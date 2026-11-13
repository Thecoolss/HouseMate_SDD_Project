// Base URLs of the two services, read by the browser at runtime.
//
// These are the local defaults for `docker compose up` (services published on
// localhost:5000 and :5001). The deploy pipeline overwrites this file with the
// Azure Container App URLs, so nothing here is hardcoded into app.js.
window.HOUSEMATE_CONFIG = {
  HOUSEHOLD_URL: "http://localhost:5000",
  FAIRNESS_URL: "http://localhost:5001",
};
