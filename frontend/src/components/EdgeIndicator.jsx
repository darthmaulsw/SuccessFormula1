/**
 * Shows the gap between our model's win probability and Polymarket's implied probability.
 * Green = model is higher than market (potential long opportunity)
 * Red   = market is higher than model (model thinks this driver is overvalued)
 */
export default function EdgeIndicator({ modelProb, marketProb, edge }) {
  if (!marketProb || marketProb === 0) return null

  const edgePct = Math.round(Math.abs(edge) * 100)
  const isPositive = edge >= 0
  const label = isPositive ? `+${edgePct}%` : `-${edgePct}%`

  return (
    <div className="flex items-center justify-between text-xs">
      <div className="flex items-center gap-3 text-gray-500">
        <span>MODEL <span className="text-white">{Math.round(modelProb * 100)}%</span></span>
        <span className="text-gray-700">·</span>
        <span>MARKET <span className="text-gray-300">{Math.round(marketProb * 100)}%</span></span>
      </div>
      {edgePct >= 1 && (
        <span
          className={`px-2 py-0.5 rounded font-bold ${
            isPositive
              ? 'bg-green-900/60 text-green-400'
              : 'bg-red-900/60 text-red-400'
          }`}
          title={isPositive ? 'Model higher than market' : 'Model lower than market'}
        >
          EDGE {label}
        </span>
      )}
    </div>
  )
}
