export const COLORS = {low:'#85512c', average:'#0867d9', elevated:'#f0cf31', flood:'#cf2929', unavailable:'#88929b'};
const number = value => value === null || value === undefined || (typeof value === 'string' && value.trim() === '') || typeof value === 'boolean' ? null : Number.isFinite(Number(value)) ? Number(value) : null;
export function position(record) {
  const values = ['discharge', 'low', 'average', 'flood'].map(key => number(record[key]));
  if (values.some(value => value === null || value < 0)) return null;
  const [q, low, average, flood] = values;
  // Degenerate or unordered reference points cannot define an interpolation.
  if (!(low < average && average < flood)) return null;
  if (q <= low) return 0;
  if (q >= flood) return 1;
  return q <= average ? 0.25 * (q-low)/(average-low) : 0.25 + 0.75 * (q-average)/(flood-average);
}
function blend(a,b,t) {
  return '#'+[1,3,5].map(i => Math.round(parseInt(a.slice(i,i+2),16)*(1-t)+parseInt(b.slice(i,i+2),16)*t).toString(16).padStart(2,'0')).join('');
}
export function color(value) {
  if (value === null || !Number.isFinite(value)) return COLORS.unavailable;
  const p = Math.max(0,Math.min(1,value));
  if (p <= 0.25) return blend(COLORS.low,COLORS.average,p/0.25);
  if (p <= 0.625) return blend(COLORS.average,COLORS.elevated,(p-0.25)/0.375);
  return blend(COLORS.elevated,COLORS.flood,(p-0.625)/0.375);
}
export function rivers(geometry, records) {
  const byId = new Map(records.map(record => [String(record.feature_id),record]));
  return {...geometry,features:geometry.features.map(feature => {
    const id = String(feature.properties.feature_id), record = byId.get(id) || {};
    const scale_position = position(record);
    return {...feature,properties:{...feature.properties,...record,feature_id:id,scale_position,color:color(scale_position)}};
  })};
}
