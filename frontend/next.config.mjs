/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // three.js / react-force-graph-3d ship browser-only code.
  transpilePackages: ["three", "react-force-graph-3d"],
};

export default nextConfig;
