import { useEffect, useState } from "react";
import { Tag } from "antd";

import { loadAirports, type AirportSummary } from "../lib/api";

export function AirportCatalog() {
  const [airports, setAirports] = useState<AirportSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    loadAirports()
      .then(setAirports)
      .catch((err) => setError(err instanceof Error ? err.message : "Catalog unavailable"));
  }, []);

  return (
    <section className="catalog-panel">
      <h2>Seeded Airport Graph</h2>
      {error && <p className="muted">{error}</p>}
      <div className="airport-grid">
        {airports.map((airport) => (
          <div className="airport-tile" key={airport.code}>
            <Tag color="blue">{airport.code}</Tag>
            <strong>{airport.name}</strong>
            <span>
              {airport.city} - {airport.terminalCount} terminals
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
