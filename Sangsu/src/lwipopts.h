#ifndef LWIPOPTS_H
#define LWIPOPTS_H

#define NO_SYS                      1
#define LWIP_RAW                    1
#define LWIP_DNS                    1
#define LWIP_DHCP                   1
#define LWIP_ALTCP                  1
#define LWIP_ALTCP_TLS              1
#define LWIP_ALTCP_TLS_MBEDTLS      1
#define LWIP_SOCKET                 0
#define LWIP_NETCONN                0

#define MEM_LIBC_MALLOC             0
#define MEM_ALIGNMENT               4
#define MEM_SIZE                    (64 * 1024)
#define MEMP_NUM_TCP_PCB            8
#define MEMP_NUM_TCP_PCB_LISTEN     4
#define MEMP_NUM_TCP_SEG            32
#define MEMP_NUM_ARP_QUEUE          10
#define MEMP_NUM_SYS_TIMEOUT        16
#define PBUF_POOL_SIZE              32
#define LWIP_ARP                    1
#define LWIP_ETHERNET               1
#define LWIP_ICMP                   1
#define LWIP_TCP                    1
#define LWIP_UDP                    1
#define TCP_WND                     8192
#define TCP_MSS                     1460
#define TCP_SND_BUF                 8192
#define TCP_SND_QUEUELEN            ((4 * TCP_SND_BUF + TCP_MSS - 1) / TCP_MSS)

#define LWIP_NETIF_STATUS_CALLBACK  1
#define LWIP_NETIF_LINK_CALLBACK    1
#define LWIP_NETIF_HOSTNAME         1

#define LWIP_STATS                  0
#define LWIP_PROVIDE_ERRNO          1

#endif
