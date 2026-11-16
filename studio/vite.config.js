export default {
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:4175",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (upstream, request) => {
            // Preserve the backend same-origin check when using the local dev proxy.
            if (request.headers.origin === `http://${request.headers.host}`) {
              upstream.setHeader("Origin", "http://127.0.0.1:4175");
            }
          });
        },
      },
    },
  },
};
