export default function MedicationIssues({ issues }) {
  return (
    <table className="data">
      <thead>
        <tr>
          <th scope="col">Drug</th>
          <th scope="col">Possible issue</th>
          <th scope="col">Suggested action</th>
          <th scope="col">Source</th>
        </tr>
      </thead>
      {/* <tbody>
        {issues.map(i => (
          <tr key={`${i.drug}-${i.issue}`}>
            <th scope="row">{i.drug}</th>
            <td>{i.issue}</td>
            <td>{i.action}</td>
            <td><span className="tag tag--blue">{i.source}</span></td>
          </tr>
        ))}
      </tbody> */}
    </table>
  )
}
