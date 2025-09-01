import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = { vus: 1, duration: '20s' };
export default function () {
  const res = http.get(`${__ENV.BASE_URL}/health`);
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
