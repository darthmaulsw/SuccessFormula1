import { useEffect, useRef } from 'react'

const KW_STYLE = {
  PIT:   'bg-yellow-900 text-yellow-300',
  TIRE:  'bg-orange-900 text-orange-300',
  SC:    'bg-blue-900 text-blue-300',
  ISSUE: 'bg-red-900 text-red-300',
}

export default function RadioFeed({ drivers }) {
  const bottomRef = useRef(null)

  // Collect all radio entries from drivers that have a last_radio transcript
  const entries = (drivers ?? [])
    .filter((d) => d.last_radio)
    .map((d) => ({
      driver_number: d.driver_number,
      name: d.name,
      team_color: d.team_color,
      transcript: d.last_radio,
      keywords: d.radio_keywords ?? [],
      sentiment: d.radio_sentiment ?? 0,
    }))

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  return (
    <div className="bg-f1gray border border-f1border rounded-lg flex flex-col h-full">
      <div className="px-4 py-2 border-b border-f1border flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-f1red live-pulse" />
        <span className="text-xs text-gray-500 font-bold tracking-widest">TEAM RADIO</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {entries.length === 0 ? (
          <p className="text-gray-600 text-xs text-center mt-8">
            Waiting for radio transmissions...
          </p>
        ) : (
          entries.map((entry, i) => (
            <div key={i} className="flex gap-2">
              <div
                className="w-0.5 rounded-full flex-shrink-0 mt-1"
                style={{ backgroundColor: entry.team_color, minHeight: '1rem' }}
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-bold text-white">{entry.name}</span>
                  {entry.keywords.map((kw) => (
                    <span
                      key={kw}
                      className={`text-[10px] px-1 py-0 rounded font-bold ${KW_STYLE[kw] ?? 'bg-gray-800 text-gray-400'}`}
                    >
                      {kw}
                    </span>
                  ))}
                  {entry.sentiment !== 0 && (
                    <span className={`text-[10px] ${entry.sentiment > 0.2 ? 'text-green-500' : entry.sentiment < -0.2 ? 'text-red-500' : 'text-gray-600'}`}>
                      {entry.sentiment > 0 ? '↑' : '↓'}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">{entry.transcript}</p>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
