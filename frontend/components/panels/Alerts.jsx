const LABEL = { high: 'High priority', moderate: 'Moderate', info: 'For information' }

export default function Alerts({ alerts }) {
  if (!alerts.length) {
    return <p style={{ margin: 0 }}>No alerts raised for this patient.</p>
  }

  return (
    <div>
      {/* {alerts.map(a => (
        <div className={`alert alert--${a.level}`} key={a.title}>
          <h4>{a.title}</h4>
          <p>{a.detail}</p>
          <p style={{ marginTop: 6 }}>
            <span className={`tag ${a.level === 'high' ? 'tag--red' : a.level === 'moderate' ? 'tag--amber' : 'tag--blue'}`}>
              {LABEL[a.level]}
            </span>
          </p>
        </div>
      ))} */}
    </div>
  )
}
