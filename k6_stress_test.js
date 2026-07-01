import http from "k6/http";
import { check, group, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://192.168.1.12:8000";

const loginDuration = new Trend("login_duration", true);
const getProfileDuration = new Trend("get_profiles_duration", true);
const saveMeasDuration = new Trend("save_measurement_duration", true);
const getMeasDuration = new Trend("get_measurements_duration", true);
const latestMeasDuration = new Trend("get_latest_measurement_duration", true);
const errorRate = new Rate("error_rate");
const successfulLogins = new Counter("successful_logins");

export const options = {
  stages: [
    { duration: "1m", target: 50 },
    { duration: "3m", target: 200 },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<500", "avg<200"],
    http_req_failed: ["rate<0.05"],
    login_duration: ["p(95)<300"],
    get_profiles_duration: ["p(95)<400"],
    save_measurement_duration: ["p(95)<400"],
    get_measurements_duration: ["p(95)<400"],
    get_latest_measurement_duration: ["p(95)<400"],
    error_rate: ["rate<0.05"],
  },
};

export function setup() {
  const uniqueId = Date.now();
  const testUser = {
    name: `StressTestUser_${uniqueId}`,
    email: `stresstest_${uniqueId}@test.com`,
    phone: `08${uniqueId}`,
    password: "TestPassword123!",
  };

  const regRes = http.post(
    `${BASE_URL}/api/auth/register`,
    JSON.stringify(testUser),
    { headers: { "Content-Type": "application/json" } }
  );

  if (regRes.status !== 200) {
    console.error(`Setup: Register failed — ${regRes.status} ${regRes.body}`);
    return null;
  }

  const regData = regRes.json();
  const userId = regData.id_user;

  const loginRes = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: testUser.email, password: testUser.password }),
    { headers: { "Content-Type": "application/json" } }
  );

  if (loginRes.status !== 200) {
    console.error(`Setup: Login failed — ${loginRes.status} ${loginRes.body}`);
    return null;
  }

  const loginData = loginRes.json();
  const token = loginData.token;

  const formData = {
    id_user: `${userId}`,
    name: "Test Profile K6",
    age: "30",
    gender: "Male",
    tb: "170.0",
    bb: "70.0",
  };

  const profileRes = http.post(
    `${BASE_URL}/api/profiles`,
    formData,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  if (profileRes.status !== 200) {
    console.error(`Setup: Create profile failed — ${profileRes.status} ${profileRes.body}`);
    return null;
  }

  const profileData = profileRes.json();

  const measPayload = {
    id_user: userId,
    id_profile: profileData.id,
    sys: 120,
    dia: 80,
    bpm: 72,
    ihb: 0,
    mov: 0,
    datetime: new Date().toISOString(),
  };

  const measRes = http.post(
    `${BASE_URL}/api/measurements`,
    JSON.stringify(measPayload),
    {
      headers: {
        "Content-Type": "application/json",
        Authorization:  `Bearer ${token}`,
      },
    }
  );

  if (measRes.status !== 200) {
    console.error(`Setup: Save measurement failed — ${measRes.status} ${measRes.body}`);
  }

  console.log(`Setup selesai: userId=${userId}, profileId=${profileData.id}`);

  return {
    userId: userId,
    profileId: profileData.id,
    email: testUser.email,
    password: testUser.password,
    token: token,
  };
}

export default function (data) {
  if (!data) {
    console.error("Setup data is null, skipping iteration.");
    return;
  }

  let token = data.token;

  group("Login", () => {
    const res = http.post(
      `${BASE_URL}/api/auth/login`,
      JSON.stringify({ email: data.email, password: data.password }),
      { headers: { "Content-Type": "application/json" } }
    );
    loginDuration.add(res.timings.duration);

    const ok = check(res, {
      "login: status 200": (r) => r.status === 200,
      "login: has token": (r) => r.json("token") !== undefined,
    });
    errorRate.add(!ok);
    if (ok) {
      successfulLogins.add(1);
      token = res.json("token") || token;
    }
  });

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  sleep(0.1);

  group("Get Profiles", () => {
    const res = http.get(`${BASE_URL}/api/profiles/${data.userId}`, { headers });
    getProfileDuration.add(res.timings.duration);

    const ok = check(res, {
      "profiles: status 200": (r) => r.status === 200,
      "profiles: is array": (r) => Array.isArray(r.json()),
    });
    errorRate.add(!ok);
  });

  sleep(0.1);

  group("Save Measurement", () => {
    const payload = {
      id_user: data.userId,
      id_profile: data.profileId,
      sys: Math.floor(Math.random() * 40) + 100,
      dia: Math.floor(Math.random() * 20) + 60,
      bpm: Math.floor(Math.random() * 30) + 60,
      ihb: Math.random() > 0.9 ? 1 : 0,
      mov: Math.random() > 0.9 ? 1 : 0,
      datetime: new Date().toISOString(),
    };

    const res = http.post(`${BASE_URL}/api/measurements`, JSON.stringify(payload), { headers });
    saveMeasDuration.add(res.timings.duration);

    const ok = check(res, {
      "save meas: status 200": (r) => r.status === 200,
      "save meas: has id": (r) => r.json("id") !== undefined,
    });
    errorRate.add(!ok);
  });

  sleep(0.1);

  group("Get Measurements", () => {
    const res = http.get(`${BASE_URL}/api/measurements/${data.profileId}`, { headers });
    getMeasDuration.add(res.timings.duration);

    const ok = check(res, {
      "get meas: status 200": (r) => r.status === 200,
      "get meas: is array": (r) => Array.isArray(r.json()),
    });
    errorRate.add(!ok);
  });

  sleep(0.1);

  group("Get Latest Measurement", () => {
    const res = http.get(`${BASE_URL}/api/measurements/${data.profileId}/latest`, { headers });
    latestMeasDuration.add(res.timings.duration);

    const ok = check(res, {
      "latest meas: status 200": (r) => r.status === 200,
      "latest meas: has sys": (r) => r.json("sys") !== undefined,
    });
    errorRate.add(!ok);
  });

  sleep(0.3 + Math.random() * 0.7);
}

export function teardown(data) {
  if (!data) return;
  console.log(`\n=== Stress Test Selesai ===`);
  console.log(`User ID: ${data.userId}, Profile ID: ${data.profileId}`);
  console.log(`Endpoint yang diuji: login, profiles, measurements, latest`);
  console.log(`===========================\n`);
}
