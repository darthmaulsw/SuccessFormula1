import EdgeIndicator from './EdgeIndicator.jsx'
import InsightBubble from './InsightBubble.jsx'

const COMPOUND_COLORS = {
  SOFT:         { bg: '#E8002D', label: 'S' },
  MEDIUM:       { bg: '#FFF200', label: 'M' },
  HARD:         { bg: '#FFFFFF', label: 'H' },
  INTERMEDIATE: { bg: '#39B54A', label: 'I' },
  WET:          { bg: '#0067FF', label: 'W' },
}

export default function DriverCard({ driver }) {
  const {
    driver_number, name, team, team_color,
    position, win_probability, polymarket_probability, edge,
    tire_compound, tire_age, pit_stops,
    last_insight, last_radio, radio_sentiment, radio_keywords,
  } = driver

  const compound = COMPOUND_COLORS[tire_compound] ?? COMPOUND_COLORS.MEDIUM
  const probPct = Math.round(win_probability * 100)

  return (
    <div className="bg-f1gray border border-f1border rounded-lg p-4 flex flex-col gap-3 hover:border-gray-600 transition-colors">
      {/* Top row: position, name, team, tire */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold text-gray-500 w-7 text-center">
            {position}
          </span>
          <div
            className="w-1 h-10 rounded-full"
            style={{ backgroundColor: team_color }}
          />
          <div>
            <div className="font-bold text-white text-sm tracking-wide">{name}</div>
            <div className="text-gray-500 text-xs">{team}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Tire badge */}
          <div className="flex items-center gap-1">
            <span
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-black"
              style={{ backgroundColor: compound.bg }}
              title={tire_compound}
            >
              {compound.label}
            </span>
            <span className="text-xs text-gray-500">{tire_age}L</span>
          </div>
          {/* Pit stops */}
          <span className="text-xs text-gray-600 ml-1">P{pit_stops}</span>
        </div>
      </div>

      {/* Win probability bar */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-gray-500">WIN PROBABILITY</span>
          <span className="text-white font-bold text-sm">{probPct}%</span>
        </div>
        <div className="w-full h-3 bg-f1border rounded-full overflow-hidden">
          <div
            className="prob-bar h-full rounded-full"
            style={{
              width: `${probPct}%`,
              backgroundColor: team_color,
              minWidth: probPct > 0 ? '4px' : '0',
            }}
          />
        </div>
      </div>

      {/* Edge indicator */}
      <EdgeIndicator
        modelProb={win_probability}
        marketProb={polymarket_probability}
        edge={edge}
      />

      {/* Radio keywords */}
      {radio_keywords.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {radio_keywords.map((kw) => (
            <span
              key={kw}
              className={`text-xs px-1.5 py-0.5 rounded font-bold ${
                kw === 'ISSUE' ? 'bg-red-900 text-red-300' :
                kw === 'PIT'   ? 'bg-yellow-900 text-yellow-300' :
                kw === 'SC'    ? 'bg-blue-900 text-blue-300' :
                                 'bg-gray-800 text-gray-400'
              }`}
            >
              {kw}
            </span>
          ))}
          {radio_sentiment !== 0 && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              radio_sentiment > 0.2 ? 'text-green-400' :
              radio_sentiment < -0.2 ? 'text-red-400' : 'text-gray-500'
            }`}>
              {radio_sentiment > 0 ? '+' : ''}{radio_sentiment.toFixed(2)}
            </span>
          )}
        </div>
      )}

      {/* K2 insight */}
      <InsightBubble insight={last_insight} />
    </div>
  )
}
