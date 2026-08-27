const BASE = 'http://localhost:8000/api'


async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const getForecast = (id) => get(`/patients/${id}/forecast`)
export const getInteractions = (id) => get(`/patients/${id}/interactions`)
export const getGuidance = (id, role) => get(`/patients/${id}/guidance?role=${role}`)

export const getMedications = (id) => get(`/patients/${id}/medications`)
export const getReview = (id) => get(`/patients/${id}/review`)

export const getPotassium = (id) => get(`/patients/${id}/potassium`)

export const getPotassiumPrediction = (id) => get(`/patients/${id}/potassium/predict`)

