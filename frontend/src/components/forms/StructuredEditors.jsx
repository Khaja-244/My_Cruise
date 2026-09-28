import {useMemo} from 'react';

function safeParse(value, fallback) {
  try {
    const parsed = JSON.parse(value || '');
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

const buttonClass = 'rounded-lg border border-default px-3 py-2 text-xs font-bold text-secondary hover:bg-surface-muted';

export function ItineraryEditor({value, onChange, ports=[]}) {
  const rows = useMemo(() => safeParse(value, [{day_number: 1, port_id: '', description: ''}]), [value]);

  const update = (index, key, nextValue) => {
    const next = rows.map((row, rowIndex) =>
      rowIndex === index ? {...row, [key]: key === 'day_number' ? Number(nextValue) : nextValue} : row
    );
    onChange(JSON.stringify(next));
  };

  const add = () => {
    const nextDay = rows.reduce((max, row) => Math.max(max, Number(row.day_number) || 0), 0) + 1;
    onChange(JSON.stringify([...rows, {day_number: nextDay, port_id: '', description: ''}]));
  };

  const remove = index => {
    const next = rows.filter((_, rowIndex) => rowIndex !== index);
    onChange(JSON.stringify(next.length ? next : [{day_number: 1, port_id: '', description: ''}]));
  };

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 className="font-bold text-primary">Itinerary</h3>
        <p className="text-xs text-muted mt-1">Add one row for each sailing day. The API receives the same JSON shape as before.</p>
      </div>
      <button type="button" className={buttonClass} onClick={add}>+ Add day</button>
    </div>
    <div className="space-y-3">
      {rows.map((row, index) => <div key={`${row.day_number}-${index}`} className="rounded-xl border border-default p-4">
        <div className="grid gap-3 md:grid-cols-[120px_1fr_1.5fr_auto]">
          <label className="text-xs font-bold text-muted">Day
            <input className="input mt-1" type="number" min="1" value={row.day_number ?? ''} onChange={e=>update(index,'day_number',e.target.value)} />
          </label>
          <label className="text-xs font-bold text-muted">Port
            <select className="input mt-1" value={row.port_id || ''} onChange={e=>update(index,'port_id',e.target.value)}>
              <option value="">At sea</option>
              {ports.map(port => <option key={port.id} value={port.id}>{port.name} — {port.city}</option>)}
            </select>
          </label>
          <label className="text-xs font-bold text-muted">Description
            <input className="input mt-1" value={row.description || ''} onChange={e=>update(index,'description',e.target.value)} placeholder="Port visit or at-sea details" />
          </label>
          <button type="button" className="self-end rounded-lg border border-error px-3 py-2 text-xs font-bold text-error hover:bg-error-soft" onClick={()=>remove(index)}>Remove</button>
        </div>
      </div>)}
    </div>
  </div>;
}

export function RefundRulesEditor({value, onChange}) {
  const rows = useMemo(() => safeParse(value, [{
    min_days_before_departure: 30,
    max_days_before_departure: '',
    refund_percent: 100,
    flat_fee_cents: 0
  }]), [value]);

  const update = (index, key, nextValue) => {
    const next = rows.map((row, rowIndex) => {
      if (rowIndex !== index) return row;
      if (key === 'max_days_before_departure') {
        return {...row, [key]: nextValue === '' ? null : Number(nextValue)};
      }
      return {...row, [key]: Number(nextValue)};
    });
    onChange(JSON.stringify(next));
  };

  const add = () => onChange(JSON.stringify([
    ...rows,
    {min_days_before_departure: 0, max_days_before_departure: null, refund_percent: 0, flat_fee_cents: 0}
  ]));

  const remove = index => {
    const next = rows.filter((_, rowIndex) => rowIndex !== index);
    onChange(JSON.stringify(next));
  };

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 className="font-bold text-primary">Refund rules</h3>
        <p className="text-xs text-muted mt-1">Ranges are validated by the backend and sent using the existing refund-rules API contract.</p>
      </div>
      <button type="button" className={buttonClass} onClick={add}>+ Add rule</button>
    </div>
    {rows.map((row,index)=><div key={index} className="rounded-xl border border-default p-4">
      <div className="grid gap-3 md:grid-cols-4">
        <label className="text-xs font-bold text-muted">Min days
          <input className="input mt-1" type="number" min="0" value={row.min_days_before_departure ?? ''} onChange={e=>update(index,'min_days_before_departure',e.target.value)} />
        </label>
        <label className="text-xs font-bold text-muted">Max days
          <input className="input mt-1" type="number" min="0" value={row.max_days_before_departure ?? ''} placeholder="No maximum" onChange={e=>update(index,'max_days_before_departure',e.target.value)} />
        </label>
        <label className="text-xs font-bold text-muted">Refund %
          <input className="input mt-1" type="number" min="0" max="100" step="0.01" value={row.refund_percent ?? ''} onChange={e=>update(index,'refund_percent',e.target.value)} />
        </label>
        <label className="text-xs font-bold text-muted">Flat fee (USD cents)
          <input className="input mt-1" type="number" min="0" value={row.flat_fee_cents ?? ''} onChange={e=>update(index,'flat_fee_cents',e.target.value)} />
        </label>
      </div>
      <button type="button" className="mt-3 text-xs font-bold text-error" onClick={()=>remove(index)}>Remove rule</button>
    </div>)}
  </div>;
}
