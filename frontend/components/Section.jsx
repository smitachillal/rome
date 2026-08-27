export default function Section({ number, title, children }) {
  return (
    <section className="card">
      <h3><span className="num">{number}</span> {title}</h3>
      <div className="card-body">{children}</div>
    </section>
  )
}
