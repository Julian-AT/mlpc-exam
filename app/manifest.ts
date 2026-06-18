import type { MetadataRoute } from "next"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MLPC Exam Trainer",
    short_name: "MLPC",
    description: "Closed-book MLPC exam practice with local progress.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f7fbfb",
    theme_color: "#f7fbfb",
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  }
}
