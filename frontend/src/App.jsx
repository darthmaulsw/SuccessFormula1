import { useSSE } from './hooks/useSSE.js'
import LapTicker from './components/LapTicker.jsx'
import DriverCard from './components/DriverCard.jsx'
import RadioFeed from './components/RadioFeed.jsx'

export default function App() {
  const { state, connected, lastUpdated } = useSSE()

  const drivers = state?.drivers ?? []
  const topDrivers = drivers.slice(0, 10) // show top 10

  return (
    <div className="min-h-screen bg-f1dark flex flex-col font-mono">
      <LapTicker
        lap={state?.lap}
        totalLaps={state?.total_laps}
        safetyCar={state?.safety_car}
        vsc={state?.vsc}
        connected={connected}
        lastUpdated={lastUpdated}
      />

      <main className="flex-1 p-4 grid grid-cols-12 gap-4 min-h-0">
        {/* Driver grid — left 8 cols */}
        <div className="col-span-8 grid grid-cols-2 gap-3 content-start">
          {drivers.length === 0 ? (
            <div className="col-span-2 flex items-center justify-center h-64 text-gray-600 text-sm">
              {connected ? 'Waiting for race data...' : 'Connecting to backend...'}
            </div>
          ) : (
            topDrivers.map((driver) => (
              <DriverCard key={driver.driver_number} driver={driver} />
            ))
          )}
        </div>

        {/* Right panel — radio feed, 4 cols */}
        <div className="col-span-4 flex flex-col gap-4 min-h-0" style={{ maxHeight: 'calc(100vh - 70px)' }}>
          <RadioFeed drivers={drivers} />

          {/* Polymarket edge summary */}
          <div className="bg-f1gray border border-f1border rounded-lg p-4 flex-shrink-0">
            <div className="text-xs text-gray-500 font-bold tracking-widest mb-3">
              TOP EDGES vs POLYMARKET
            </div>
            <div className="space-y-2">
              {drivers
                .filter((d) => Math.abs(d.edge) >= 0.03)
                .sort((a, b) => Math.abs(b.edge) - Math.abs(a.edge))
                .slice(0, 5)
                .map((d) => (
                  <div key={d.driver_number} className="flex items-center justify-between text-xs">
                    <span className="text-gray-300">{d.name}</span>
                    <span
                      className={`font-bold ${d.edge > 0 ? 'text-green-400' : 'text-red-400'}`}
                    >
                      {d.edge > 0 ? '+' : ''}{Math.round(d.edge * 100)}%
                    </span>
                  </div>
                ))}
              {drivers.filter((d) => Math.abs(d.edge) >= 0.03).length === 0 && (
                <p className="text-gray-600 text-xs">No significant edges detected</p>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
