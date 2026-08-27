export default function Tabs({ tabs, active, onChange }) {
  function onKeyDown(e) {
    const i = tabs.findIndex(t => t.id === active)
    if (e.key === 'ArrowRight') onChange(tabs[(i + 1) % tabs.length].id)
    if (e.key === 'ArrowLeft') onChange(tabs[(i - 1 + tabs.length) % tabs.length].id)
  }

  return (
    <div className="tabs" role="tablist" aria-label="Dashboard sections" onKeyDown={onKeyDown}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          id={`tab-${tab.id}`}
          className="tab"
          role="tab"
          type="button"
          aria-selected={active === tab.id}
          aria-controls={`panel-${tab.id}`}
          tabIndex={active === tab.id ? 0 : -1}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
