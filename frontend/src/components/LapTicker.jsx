export default function LapTicker({ lap, totalLaps, safetyCar, vsc, connected, lastUpdated }) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-f1gray border-b border-f1border">
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <span className="text-f1red font-bold text-xl tracking-widest">SF1</span>
        <span className="text-gray-500 text-sm">RACE PREDICTION</span>
      </div>

      {/* Center: Race status */}
      <div className="flex items-center gap-4 text-sm font-mono">
        {safetyCar && (
          <span className="bg-yellow-500 text-black px-2 py-0.5 rounded font-bold live-pulse">
            SAFETY CAR
          </span>
        )}
        {vsc && (
          <span className="bg-yellow-400 text-black px-2 py-0.5 rounded font-bold live-pulse">
            VSC
          </span>
        )}
        <span className="text-white font-bold text-lg">
          LAP {lap ?? '—'} / {totalLaps ?? 53}
        </span>
        <div className="w-32 h-1.5 bg-f1border rounded-full overflow-hidden">
          <div
            className="h-full bg-f1red rounded-full transition-all duration-1000"
            style={{ width: `${lap && totalLaps ? (lap / totalLaps) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Right: Connection status */}
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span
          className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 live-pulse' : 'bg-red-600'}`}
        />
        <span>{connected ? 'LIVE' : 'RECONNECTING'}</span>
        {lastUpdated && (
          <span className="text-gray-600">
            {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>
    </header>
  )
}
