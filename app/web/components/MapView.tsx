"use client";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

type R = { region: string; value: number; lat?: number | null; lng?: number | null };

export default function MapView({ regions }: { regions: R[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const pts = regions.filter((r) => r.lat != null && r.lng != null && r.value != null);
    if (!ref.current || !pts.length) return;
    const vals = pts.map((p) => p.value);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals) > lo ? Math.max(...vals) : lo + 1;

    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
      center: [pts[0].lng!, pts[0].lat!],
      zoom: 8,
      attributionControl: false,
    });
    map.on("load", () => {
      map.addSource("regions", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: pts.map((p) => ({
            type: "Feature",
            properties: { value: p.value, region: p.region },
            geometry: { type: "Point", coordinates: [p.lng!, p.lat!] },
          })),
        } as any,
      });
      map.addLayer({
        id: "r", type: "circle", source: "regions",
        paint: {
          "circle-radius": 6,
          "circle-color": ["interpolate", ["linear"], ["get", "value"], lo, "#E7F0EC", hi, "#10644C"],
          "circle-opacity": 0.85,
          "circle-stroke-width": 0.5,
          "circle-stroke-color": "#ffffff",
        },
      });
      const b = new maplibregl.LngLatBounds();
      pts.forEach((p) => b.extend([p.lng!, p.lat!]));
      map.fitBounds(b, { padding: 28, maxZoom: 11, duration: 0 });
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mousemove", "r", (e: any) => {
        const f = e.features[0];
        popup.setLngLat(e.lngLat)
          .setHTML(`<b>${f.properties.region}</b><br/>${Math.round(f.properties.value).toLocaleString()}`)
          .addTo(map);
      });
      map.on("mouseleave", "r", () => popup.remove());
    });
    return () => map.remove();
  }, [regions]);

  return <div ref={ref} className="h-72 w-full overflow-hidden rounded-lg border border-black/[0.06]" />;
}
