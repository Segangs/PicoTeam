-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.users (
  userId integer NOT NULL,
  userAccountId character varying DEFAULT NULL::character varying,
  userPassword character varying DEFAULT NULL::character varying,
  userName character varying DEFAULT NULL::character varying,
  userPhoneNumber character varying DEFAULT NULL::character varying,
  userPaymentStatus character varying DEFAULT NULL::character varying,
  userCreateDate timestamp without time zone,
  userActiveStatus character varying DEFAULT NULL::character varying,
  CONSTRAINT users_pkey PRIMARY KEY (userId)
);
CREATE TABLE public.usim (
  usimId integer NOT NULL,
  usimMNO character varying DEFAULT NULL::character varying,
  usimIMSI character varying DEFAULT NULL::character varying,
  usimICCID character varying DEFAULT NULL::character varying,
  CONSTRAINT usim_pkey PRIMARY KEY (usimId)
);
CREATE TABLE public.machine (
  machineId integer NOT NULL,
  systemType character varying DEFAULT NULL::character varying,
  modelName character varying DEFAULT NULL::character varying,
  manufacturer character varying DEFAULT NULL::character varying,
  machineRegDate date,
  machineStatus smallint,
  CONSTRAINT machine_pkey PRIMARY KEY (machineId)
);
CREATE TABLE public.userworkplace (
  userWorkplaceId integer NOT NULL,
  userId integer,
  WorkplaceAddress character varying DEFAULT NULL::character varying,
  WorkplaceType character varying DEFAULT NULL::character varying,
  WorkplaceAddressRegDate timestamp without time zone,
  CONSTRAINT userworkplace_pkey PRIMARY KEY (userWorkplaceId),
  CONSTRAINT fk_uswp_userId FOREIGN KEY (userId) REFERENCES public.users(userId)
);
CREATE TABLE public.device (
  deviceId integer NOT NULL,
  deviceType character varying DEFAULT NULL::character varying,
  deviceSerialNumber character varying DEFAULT NULL::character varying,
  deviceIMEI character varying DEFAULT NULL::character varying,
  deviceStatus character varying DEFAULT NULL::character varying,
  usimId integer,
  userId integer,
  userWorkplaceId integer,
  CONSTRAINT device_pkey PRIMARY KEY (deviceId),
  CONSTRAINT fk_device_userWorkplaceId FOREIGN KEY (userWorkplaceId) REFERENCES public.userworkplace(userWorkplaceId),
  CONSTRAINT fk_device_usimId FOREIGN KEY (usimId) REFERENCES public.usim(usimId)
);
CREATE TABLE public.sensor (
  sensorId integer NOT NULL,
  sensorModelName character varying DEFAULT NULL::character varying,
  sensorType character varying DEFAULT NULL::character varying,
  sensorMemo character varying DEFAULT NULL::character varying,
  deviceId integer,
  CONSTRAINT sensor_pkey PRIMARY KEY (sensorId),
  CONSTRAINT fk_se_deviceId FOREIGN KEY (deviceId) REFERENCES public.device(deviceId)
);
CREATE TABLE public.sensorvalue (
  sensorValueId integer NOT NULL,
  sensorId integer,
  sensorValue numeric DEFAULT NULL::numeric,
  sensorvaluetime timestamp without time zone,
  CONSTRAINT sensorvalue_pkey PRIMARY KEY (sensorValueId),
  CONSTRAINT fk_se_sensorId FOREIGN KEY (sensorId) REFERENCES public.sensor(sensorId)
);
CREATE TABLE public.usermachine (
  userMachineId integer NOT NULL,
  machineId integer,
  deviceId integer,
  userMachineManufactureDate date,
  userMachineRegDate date,
  CONSTRAINT usermachine_pkey PRIMARY KEY (userMachineId),
  CONSTRAINT fk_usermachine_deviceId FOREIGN KEY (deviceId) REFERENCES public.device(deviceId),
  CONSTRAINT fk_usermachine_machineId FOREIGN KEY (machineId) REFERENCES public.machine(machineId)
);
CREATE TABLE public.alertsend (
  alertSendId integer NOT NULL,
  userId integer,
  userMachineId integer,
  sensorValueId integer,
  alertSendDate timestamp without time zone,
  CONSTRAINT alertsend_pkey PRIMARY KEY (alertSendId),
  CONSTRAINT fk_al_userId FOREIGN KEY (userId) REFERENCES public.users(userId),
  CONSTRAINT fk_al_sensorValueId FOREIGN KEY (sensorValueId) REFERENCES public.sensorvalue(sensorValueId),
  CONSTRAINT fk_al_userMachineId FOREIGN KEY (userMachineId) REFERENCES public.usermachine(userMachineId)
);
CREATE TABLE public.payment (
  paymentId integer NOT NULL,
  userId integer,
  paymentAmount integer,
  paymentDate date,
  StartUsagePeriod date,
  EndUsagePeriod date,
  CONSTRAINT payment_pkey PRIMARY KEY (paymentId),
  CONSTRAINT fk_pa_userId FOREIGN KEY (userId) REFERENCES public.users(userId)
);
CREATE TABLE public.repairlog (
  repairLogId integer NOT NULL,
  userId integer,
  userMachineId integer,
  repairDate timestamp without time zone,
  repairMemo character varying DEFAULT NULL::character varying,
  repairCosts integer,
  CONSTRAINT repairlog_pkey PRIMARY KEY (repairLogId),
  CONSTRAINT fk_re_userId FOREIGN KEY (userId) REFERENCES public.users(userId),
  CONSTRAINT fk_re_usermachineId FOREIGN KEY (userMachineId) REFERENCES public.usermachine(userMachineId)
);
CREATE TABLE public.usersettings (
  userSettingsId integer NOT NULL,
  userMachineId integer,
  tempUpperLimitValue numeric DEFAULT NULL::numeric,
  tempLowerLimitValue numeric DEFAULT NULL::numeric,
  CONSTRAINT usersettings_pkey PRIMARY KEY (userSettingsId),
  CONSTRAINT fk_us_userMachineId FOREIGN KEY (userMachineId) REFERENCES public.usermachine(userMachineId)
);
CREATE TABLE public.board (
  boardId integer NOT NULL DEFAULT nextval('"board_boardId_seq"'::regclass),
  title character varying NOT NULL,
  content text NOT NULL,
  userId integer,
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT board_pkey PRIMARY KEY (boardId),
  CONSTRAINT board_userId_fkey FOREIGN KEY (userId) REFERENCES public.users(userId)
);