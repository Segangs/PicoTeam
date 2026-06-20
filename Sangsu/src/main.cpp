#include <cstdio>
#include <cstring>
#include <string>

#include "pico/cyw43_arch.h"
#include "pico/rand.h"
#include "pico/stdlib.h"

#include "lwip/altcp.h"
#include "lwip/altcp_tls.h"
#include "lwip/dns.h"
#include "lwip/pbuf.h"

#include "mbedtls/ssl.h"

namespace {

constexpr const char* kWifiSsid = "bindsoft";
constexpr const char* kWifiPassword = "bindsoft24";

constexpr const char* kDeviceId = "2026000003";
constexpr const char* kDeviceImei = "351234567890003";

#ifndef SUPABASE_HOST
#define SUPABASE_HOST "YOUR_SUPABASE_HOST_PLACEHOLDER"
#endif

#ifndef SUPABASE_ANON_KEY
#define SUPABASE_ANON_KEY "YOUR_SUPABASE_ANON_KEY_PLACEHOLDER"
#endif

constexpr const char* kSupabaseHost = SUPABASE_HOST;
constexpr const char* kSupabasePath = "/rest/v1/rpc/insert_sensor_value";
constexpr const char* kSupabaseApiKey = SUPABASE_ANON_KEY;

constexpr uint16_t kHttpsPort = 443;
constexpr int kSendIntervalMs = 60 * 1000;
constexpr int kDnsTimeoutMs = 10000;
constexpr int kHttpsTimeoutMs = 20000;
constexpr int kWifiRetryDelayMs = 10000;

struct DnsState {
    ip_addr_t address{};
    volatile bool done = false;
    volatile bool failed = false;
};

struct HttpsState {
    altcp_pcb* pcb = nullptr;
    std::string request;
    std::string response;
    volatile bool connected = false;
    volatile bool sent = false;
    volatile bool done = false;
    volatile bool failed = false;
};

struct ScanState {
    volatile bool found = false;
    int best_rssi = -999;
    uint16_t channel = 0;
    uint8_t auth_mode = 0;
};

struct WifiAuthMode {
    uint32_t auth;
    const char* name;
};

constexpr WifiAuthMode kWifiAuthModes[] = {
    {CYW43_AUTH_WPA2_AES_PSK, "WPA2_AES"},
    {CYW43_AUTH_WPA2_MIXED_PSK, "WPA2_MIXED"},
    {CYW43_AUTH_WPA3_WPA2_AES_PSK, "WPA3_WPA2"},
    {CYW43_AUTH_WPA_TKIP_PSK, "WPA_TKIP"},
};

void set_led(bool on) {
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on ? 1 : 0);
}

void blink_led(int count, int on_ms = 150, int off_ms = 150) {
    for (int i = 0; i < count; ++i) {
        set_led(true);
        sleep_ms(on_ms);
        set_led(false);
        sleep_ms(off_ms);
    }
}

int scan_callback(void* env, const cyw43_ev_scan_result_t* result) {
    auto* state = static_cast<ScanState*>(env);
    if (result == nullptr) {
        return 0;
    }

    char ssid[33]{};
    const size_t ssid_len = result->ssid_len < sizeof(ssid) - 1
                                ? result->ssid_len
                                : sizeof(ssid) - 1;
    std::memcpy(ssid, result->ssid, ssid_len);

    std::printf(
        "Scan: SSID=%s channel=%u rssi=%d auth=0x%02x\n",
        ssid,
        result->channel,
        result->rssi,
        result->auth_mode);

    if (std::strcmp(ssid, kWifiSsid) == 0) {
        state->found = true;
        if (result->rssi > state->best_rssi) {
            state->best_rssi = result->rssi;
            state->channel = result->channel;
            state->auth_mode = result->auth_mode;
        }
    }

    return 0;
}

bool scan_for_wifi() {
    ScanState state{};
    cyw43_wifi_scan_options_t scan_options{};

    cyw43_arch_lwip_begin();
    const int scan_result =
        cyw43_wifi_scan(&cyw43_state, &scan_options, &state, scan_callback);
    cyw43_arch_lwip_end();

    if (scan_result != 0) {
        std::printf("Wi-Fi scan start failed: %d\n", scan_result);
        return true;
    }

    const absolute_time_t deadline = make_timeout_time_ms(10000);
    while (cyw43_wifi_scan_active(&cyw43_state) && !time_reached(deadline)) {
        sleep_ms(100);
    }

    if (state.found) {
        std::printf(
            "Target SSID found: %s channel=%u rssi=%d auth=0x%02x\n",
            kWifiSsid,
            state.channel,
            state.best_rssi,
            state.auth_mode);
    } else {
        std::printf("Target SSID not found: %s\n", kWifiSsid);
    }

    return state.found;
}

float make_sensor_value() {
    const uint32_t raw = get_rand_32();
    const int tenths = -100 + static_cast<int>(raw % 171);
    return static_cast<float>(tenths) / 10.0f;
}

std::string make_rpc_body(float sensor_value) {
    char body[96];
    std::snprintf(
        body,
        sizeof(body),
        "{\"p_imei\":\"%s\",\"p_value\":%.1f}",
        kDeviceImei,
        sensor_value);
    return std::string(body);
}

std::string make_display_payload(float sensor_value) {
    char body[128];
    std::snprintf(
        body,
        sizeof(body),
        "{\"deviceId\":\"%s\",\"deviceIMEI\":\"%s\",\"sensorValue\":%.1f}",
        kDeviceId,
        kDeviceImei,
        sensor_value);
    return std::string(body);
}

std::string make_http_request(const std::string& body) {
    char header[768];
    std::snprintf(
        header,
        sizeof(header),
        "POST %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "User-Agent: pico2w-supabase/1.0\r\n"
        "apikey: %s\r\n"
        "Authorization: Bearer %s\r\n"
        "Content-Type: application/json\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n"
        "Content-Length: %u\r\n"
        "\r\n",
        kSupabasePath,
        kSupabaseHost,
        kSupabaseApiKey,
        kSupabaseApiKey,
        static_cast<unsigned>(body.size()));

    std::string request(header);
    request += body;
    return request;
}

void dns_found_callback(const char*, const ip_addr_t* ipaddr, void* arg) {
    auto* state = static_cast<DnsState*>(arg);
    if (ipaddr == nullptr) {
        state->failed = true;
    } else {
        state->address = *ipaddr;
    }
    state->done = true;
}

bool resolve_host(ip_addr_t* address) {
    DnsState state{};

    cyw43_arch_lwip_begin();
    const err_t err =
        dns_gethostbyname(kSupabaseHost, address, dns_found_callback, &state);
    cyw43_arch_lwip_end();

    if (err == ERR_OK) {
        return true;
    }

    if (err != ERR_INPROGRESS) {
        std::printf("DNS request failed for %s: %d\n", kSupabaseHost, err);
        return false;
    }

    const absolute_time_t deadline = make_timeout_time_ms(kDnsTimeoutMs);
    while (!state.done && !time_reached(deadline)) {
        sleep_ms(10);
    }

    if (!state.done || state.failed) {
        std::printf("DNS lookup timed out or failed for %s\n", kSupabaseHost);
        return false;
    }

    *address = state.address;
    return true;
}

void close_connection(HttpsState* state) {
    cyw43_arch_lwip_begin();
    if (state->pcb != nullptr) {
        altcp_arg(state->pcb, nullptr);
        altcp_recv(state->pcb, nullptr);
        altcp_sent(state->pcb, nullptr);
        altcp_err(state->pcb, nullptr);
        altcp_close(state->pcb);
        state->pcb = nullptr;
    }
    cyw43_arch_lwip_end();
}

void abort_connection(HttpsState* state) {
    cyw43_arch_lwip_begin();
    if (state->pcb != nullptr) {
        altcp_arg(state->pcb, nullptr);
        altcp_recv(state->pcb, nullptr);
        altcp_sent(state->pcb, nullptr);
        altcp_err(state->pcb, nullptr);
        altcp_abort(state->pcb);
        state->pcb = nullptr;
    }
    cyw43_arch_lwip_end();
}

void https_error_callback(void* arg, err_t err) {
    auto* state = static_cast<HttpsState*>(arg);
    state->pcb = nullptr;
    state->failed = true;
    std::printf("HTTPS error: %d\n", err);
}

err_t https_sent_callback(void* arg, altcp_pcb*, u16_t) {
    auto* state = static_cast<HttpsState*>(arg);
    state->sent = true;
    return ERR_OK;
}

err_t https_recv_callback(void* arg, altcp_pcb* pcb, pbuf* p, err_t err) {
    auto* state = static_cast<HttpsState*>(arg);

    if (err != ERR_OK) {
        state->failed = true;
        return err;
    }

    if (p == nullptr) {
        state->done = true;
        return ERR_OK;
    }

    for (pbuf* q = p; q != nullptr; q = q->next) {
        state->response.append(
            static_cast<const char*>(q->payload),
            static_cast<size_t>(q->len));
    }

    altcp_recved(pcb, p->tot_len);
    pbuf_free(p);
    return ERR_OK;
}

err_t https_connected_callback(void* arg, altcp_pcb* pcb, err_t err) {
    auto* state = static_cast<HttpsState*>(arg);
    if (err != ERR_OK) {
        state->failed = true;
        return err;
    }

    state->connected = true;
    altcp_recv(pcb, https_recv_callback);
    altcp_sent(pcb, https_sent_callback);

    err = altcp_write(
        pcb,
        state->request.data(),
        static_cast<u16_t>(state->request.size()),
        TCP_WRITE_FLAG_COPY);
    if (err != ERR_OK) {
        state->failed = true;
        return err;
    }

    return altcp_output(pcb);
}

int parse_http_status(const std::string& response) {
    int status = 0;
    if (std::sscanf(response.c_str(), "HTTP/%*s %d", &status) == 1) {
        return status;
    }
    return 0;
}

bool send_once() {
    ip_addr_t server_address{};
    if (!resolve_host(&server_address)) {
        return false;
    }

    const float sensor_value = make_sensor_value();
    const std::string display_payload = make_display_payload(sensor_value);
    const std::string rpc_body = make_rpc_body(sensor_value);

    HttpsState state{};
    state.request = make_http_request(rpc_body);

    altcp_tls_config* tls_config = altcp_tls_create_config_client(nullptr, 0);
    if (tls_config == nullptr) {
        std::printf("TLS config allocation failed\n");
        return false;
    }

    cyw43_arch_lwip_begin();
    state.pcb = altcp_tls_new(tls_config, IPADDR_TYPE_V4);
    if (state.pcb != nullptr) {
        auto* ssl = static_cast<mbedtls_ssl_context*>(altcp_tls_context(state.pcb));
        if (ssl != nullptr) {
            mbedtls_ssl_set_hostname(ssl, kSupabaseHost);
        }

        altcp_arg(state.pcb, &state);
        altcp_err(state.pcb, https_error_callback);
        const err_t err = altcp_connect(
            state.pcb,
            &server_address,
            kHttpsPort,
            https_connected_callback);
        if (err != ERR_OK) {
            altcp_abort(state.pcb);
            state.pcb = nullptr;
            state.failed = true;
        }
    }
    cyw43_arch_lwip_end();

    if (state.pcb == nullptr) {
        altcp_tls_free_config(tls_config);
        std::printf("HTTPS connection allocation/connect failed\n");
        return false;
    }

    const absolute_time_t deadline = make_timeout_time_ms(kHttpsTimeoutMs);
    while (!state.done && !state.failed && !time_reached(deadline)) {
        sleep_ms(10);
    }

    bool success = false;
    if (state.done) {
        const int status = parse_http_status(state.response);
        success = (status >= 200 && status < 300);
        std::printf(
            "Payload: %s\nRPC body: %s\nHTTP status: %d\n",
            display_payload.c_str(),
            rpc_body.c_str(),
            status);
        if (!success) {
            std::printf("Response:\n%s\n", state.response.c_str());
        }
        close_connection(&state);
    } else {
        std::printf("HTTPS request timed out or failed\n");
        abort_connection(&state);
    }

    altcp_tls_free_config(tls_config);
    return success;
}

}  // namespace

int main() {
    stdio_init_all();
    sleep_ms(2000);

    std::printf("Starting Pico 2 W Supabase temperature sender\n");

    if (cyw43_arch_init_with_country(CYW43_COUNTRY_SOUTH_KOREA) != 0) {
        std::printf("Wi-Fi chip init failed\n");
        return 1;
    }

    cyw43_arch_enable_sta_mode();
    blink_led(2, 80, 80);

    while (true) {
        if (!scan_for_wifi()) {
            blink_led(5, 180, 180);
            sleep_ms(kWifiRetryDelayMs);
            continue;
        }

        bool connected = false;
        for (const auto& mode : kWifiAuthModes) {
            std::printf(
                "Connecting to Wi-Fi SSID: %s using %s\n",
                kWifiSsid,
                mode.name);
            const int wifi_result = cyw43_arch_wifi_connect_timeout_ms(
                kWifiSsid,
                kWifiPassword,
                mode.auth,
                30000);

            if (wifi_result == 0) {
                connected = true;
                break;
            }

            std::printf(
                "Wi-Fi connect failed with %s: %d\n",
                mode.name,
                wifi_result);
            blink_led(3, 250, 250);
            sleep_ms(1000);
        }

        if (connected) {
            break;
        }

        std::printf("All Wi-Fi auth modes failed. Retrying...\n");
        sleep_ms(kWifiRetryDelayMs);
    }

    std::printf("Wi-Fi connected\n");
    blink_led(4, 80, 80);

    while (true) {
        const bool ok = send_once();
        if (ok) {
            std::printf("Supabase send succeeded\n");
            blink_led(2, 500, 200);
        } else {
            std::printf("Supabase send failed\n");
            blink_led(6, 100, 100);
        }
        sleep_ms(kSendIntervalMs);
    }
}
