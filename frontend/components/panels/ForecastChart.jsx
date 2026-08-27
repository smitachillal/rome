import React, { useEffect, useState } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceDot,
} from 'recharts'
import { getForecast } from '../../api/client.js'

const TEAL = '#0b6b5b', AMBER = '#b26a00', RED = '#a3231f', MUT = '#5c6b68'

export default function ForecastChart({ patientId }) {
  const [f, setF] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (patientId == null) return
    setF(null); setErr(null)
    getForecast(patientId).then(setF).catch((e) => setErr(String(e)))
  }, [patientId])

  if (err) return <div className="rec-empty">Could not load forecast ({err}).</div>
  if (!f) return <div className="rec-empty">Loading forecast…</div>
  if (!f.ok) return <div className="rec-empty">Forecast unavailable: {f.reason}</div>

  // merge history + forecast into one series for the chart
  const hist = f.history.map((h) => ({ date: h.date, actual: h.egfr }))
  const fc = f.forecast.map((p) => ({
    date: p.date, projected: p.egfr, lower: p.lower,
    band: [p.lower, p.upper],   // area range
  }))
  // connect: last actual point also seeds the projected line
  if (hist.length && fc.length) fc[0].projected = hist[hist.length - 1].actual
  const data = [...hist, ...fc]

  const br = f.breach
  const breachPoint = br.projected
    ? fc.reduce((best, p) => Math.abs(new Date(p.date) - new Date(br.date)) <
        Math.abs(new Date(best.date) - new Date(br.date)) ? p : best, fc[0])
    : null

  return (
    <div className="section">
      <div className="forecast-headline">
        {br.projected ? (
          <>
            <span className="fc-big">{br.days}</span>
            <span className="fc-unit">days to eGFR {br.threshold}</span>
            <span className="fc-range">
              (range {br.range_days[0] ?? '—'}–{br.range_days[1] ?? 'no breach'} days · projected {br.date})
            </span>
          </>
        ) : (
          <span className="fc-stable">No threshold breach projected — trajectory stable or improving.</span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 8, right: 14, bottom: 4, left: -10 }}>
          <CartesianGrid stroke="#eef3f1" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: MUT }} minTickGap={40} />
          <YAxis domain={[0, 'dataMax + 10']} tick={{ fontSize: 11, fill: MUT }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          {/* uncertainty cone */}
          <Area dataKey="band" stroke="none" fill={TEAL} fillOpacity={0.12} isAnimationActive={false} />
          {/* threshold lines */}
          {f.next_threshold && (
            <ReferenceLine y={f.next_threshold} stroke={RED} strokeDasharray="5 4"
              label={{ value: `eGFR ${f.next_threshold}`, fontSize: 10, fill: RED, position: 'insideTopRight' }} />
          )}
          <ReferenceLine y={45} stroke={AMBER} strokeDasharray="3 4" />
          {/* historical actual */}
          <Line dataKey="actual" stroke={TEAL} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} connectNulls />
          {/* projected */}
          <Line dataKey="projected" stroke={TEAL} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} connectNulls />
          {/* breach marker */}
          {breachPoint && (
            <ReferenceDot x={breachPoint.date} y={f.next_threshold} r={6} fill={RED} stroke="#fff" strokeWidth={2} />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="fc-foot">
        Trend {f.slope_per_year}/yr · fit R² {f.r2} · solid = measured, dashed = projected,
        shaded = 95% prediction interval. Advisory only.
      </div>
    </div>
  )
}
