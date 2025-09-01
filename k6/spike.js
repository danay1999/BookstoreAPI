import http from 'k6/http';
export const options = {
  scenarios: {
    spike: {
      executor: 'ramping-arrival-rate',
      startRate: 20, timeUnit: '1s',
      stages: [
        { target: 200, duration: '45s' },
        { target: 200, duration: '2m'  },
        { target: 20,  duration: '1m'  },
      ],
      preAllocatedVUs: 200, maxVUs: 1000
    }
  }
};
export default function () {
  http.get(`${__ENV.BASE_URL}/books?limit=20`);
}
