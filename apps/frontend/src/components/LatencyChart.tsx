import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip
} from "chart.js";
import { Bar } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export function LatencyChart() {
  return (
    <div className="chart-panel">
      <h2>Demo Latency Budget</h2>
      <Bar
        data={{
          labels: ["Express API", "Semantic", "Cypher", "LLM/mock", "Mongo write"],
          datasets: [
            {
              label: "Target ms",
              data: [45, 90, 120, 120, 25],
              backgroundColor: ["#2f6f73", "#c46a3a", "#536dfe", "#7b5ea7", "#6c7a36"]
            }
          ]
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: "milliseconds" } }
          }
        }}
      />
    </div>
  );
}

