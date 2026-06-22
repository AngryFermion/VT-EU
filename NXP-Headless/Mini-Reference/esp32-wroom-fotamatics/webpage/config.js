// SmartWheels dashboard — API endpoint configuration
//
// When running locally via server.py, leave SW_API_BASE as '' (empty).
// Relative paths (/api/...) will resolve to the local server automatically.
//
// When hosting on ancitconsulting.com, set SW_API_BASE to your Cloudflare
// Tunnel URL (see README for setup). Example:
//   var SW_API_BASE = 'https://smartwheels.your-domain.com';
//
// Point to your local server.py when running FOTA from the hosted website.
// Start server.py first:  python webpage/server.py
// Then visit https://www.ancitconsulting.com/telematics/ — FOTA will reach
// http://localhost:5000 on your machine via Private Network Access.
var SW_API_BASE = 'http://localhost:5000';
