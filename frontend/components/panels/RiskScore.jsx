const BAND_TONE = { High: 'tag--red', Moderate: 'tag--amber', Low: 'tag--green' }

export default function RiskScore({ risk }) {
  // const max = Math.max(...risk.shap.map(f => Math.abs(f.value)))
  // const ordered = [...risk.shap].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))

  return (
    <>
      {/* <div className="risk-head">
        <span className="risk-value tabular">{risk.score.toFixed(2)}</span>
        <div>
          <span className={`tag ${BAND_TONE[risk.band]}`}>{risk.band} risk</span>
          <p className="risk-caption" style={{ margin: '6px 0 0' }}>
            {risk.outcome} · model {risk.modelVersion}
          </p>
        </div>
      </div>

      <div className="shap">
        {ordered.map(f => {
          const width = (Math.abs(f.value) / max) * 50
          const up = f.value > 0
          return (
            <div className="shap-row" key={f.feature}>
              <span>{f.feature}</span>
              <span className="shap-track">
                <span
                  className={`shap-bar ${up ? 'shap-bar--up' : 'shap-bar--down'}`}
                  style={{ width: `${width}%` }}
                />
              </span>
              <span className="tabular" style={{ textAlign: 'right', color: up ? 'var(--nhs-red)' : 'var(--nhs-bright-blue)' }}>
                {up ? '+' : ''}{f.value.toFixed(2)}
              </span>
            </div>
          )
        })}
      </div> */}

      <div className="shap-axis">
        <span />
        <span><span>lowers risk</span><span>raises risk</span></span>
        <span />
      </div>
    </>
  )
}
