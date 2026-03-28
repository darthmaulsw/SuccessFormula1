export default function InsightBubble({ insight }) {
  if (!insight || insight === 'Analyzing...') {
    return (
      <p className="text-xs text-gray-600 italic">Analyzing...</p>
    )
  }

  return (
    <div className="border-l-2 border-gray-700 pl-2">
      <p className="text-xs text-gray-400 leading-relaxed">{insight}</p>
      <span className="text-[10px] text-gray-600 mt-0.5 block">K2 Think V2</span>
    </div>
  )
}
