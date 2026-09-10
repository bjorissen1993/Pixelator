import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';

type FormState = {
  name:string; concept:string; appearance:string; clothing:string; spirit:boolean;
  camera:'high-top-down'|'low-top-down'|'front'; sprite_size:number; palette_colors:number;
  detail:'simple'|'balanced'|'high'; outline:'none'|'soft'|'dark'; seed?:number;
};

const initial: FormState = {
  name:'Berwynn', concept:'elderly former village chief spirit',
  appearance:'short messy grey hair, thick rough grey beard, tired stern but kind face, broad shoulders',
  clothing:'worn dark tunic, faded chief mantle, simple cloth belt, no armor',
  spirit:true, camera:'high-top-down', sprite_size:48, palette_colors:40, detail:'high', outline:'soft'
};

function App(){
  const [form,setForm]=useState<FormState>(initial);
  const [loading,setLoading]=useState(false);
  const [result,setResult]=useState<any>(null);
  const [error,setError]=useState('');
  const set=(k:keyof FormState,v:any)=>setForm(f=>({...f,[k]:v}));
  const generate=async()=>{
    setLoading(true);setError('');setResult(null);
    try{
      const r=await fetch('http://localhost:8000/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(form)});
      const data=await r.json(); if(!r.ok) throw new Error(data.detail||'Generation failed'); setResult(data);
    }catch(e:any){setError(e.message)} finally{setLoading(false)}
  };
  const download=(url:string,name:string)=>{const a=document.createElement('a');a.href=url;a.download=name;a.click()};

  return <main className="shell">
    <section className="hero"><div><span className="eyebrow">FREAKY DEV / CHIMERA</span><h1>Pixel Generator</h1><p>Local-first character generation with Chimera-specific spirit rules.</p></div><div className="badge">48×48 ready</div></section>
    <section className="grid">
      <div className="panel form">
        <label>Name<input value={form.name} onChange={e=>set('name',e.target.value)}/></label>
        <label>Concept<textarea value={form.concept} onChange={e=>set('concept',e.target.value)}/></label>
        <label>Appearance<textarea value={form.appearance} onChange={e=>set('appearance',e.target.value)}/></label>
        <label>Clothing<textarea value={form.clothing} onChange={e=>set('clothing',e.target.value)}/></label>
        <div className="row">
          <label>Camera<select value={form.camera} onChange={e=>set('camera',e.target.value)}><option value="high-top-down">High top-down</option><option value="low-top-down">Low top-down</option><option value="front">Front</option></select></label>
          <label>Sprite<select value={form.sprite_size} onChange={e=>set('sprite_size',+e.target.value)}>{[32,48,56,64].map(x=><option key={x} value={x}>{x}×{x}</option>)}</select></label>
        </div>
        <div className="row">
          <label>Detail<select value={form.detail} onChange={e=>set('detail',e.target.value)}><option value="simple">Simple</option><option value="balanced">Balanced</option><option value="high">High</option></select></label>
          <label>Outline<select value={form.outline} onChange={e=>set('outline',e.target.value)}><option value="none">None</option><option value="soft">Soft</option><option value="dark">Dark</option></select></label>
        </div>
        <label>Palette colors<input type="number" min="8" max="128" value={form.palette_colors} onChange={e=>set('palette_colors',+e.target.value)}/></label>
        <label className="check"><input type="checkbox" checked={form.spirit} onChange={e=>set('spirit',e.target.checked)}/>Spirit body — force no legs + spectral tail</label>
        <button onClick={generate} disabled={loading}>{loading?'Generating locally…':'Generate character'}</button>
        {error&&<p className="error">{error}</p>}
      </div>
      <div className="panel preview">
        {!result?<div className="empty"><strong>Character preview</strong><span>Your generated sprite appears here.</span></div>:<>
          <img src={result.preview_data_url} className="sprite"/>
          <div className="actions"><button onClick={()=>download(result.sprite_data_url,`${form.name.toLowerCase()}-${form.sprite_size}px.png`)}>Download sprite</button><button className="secondary" onClick={()=>download(result.preview_data_url,`${form.name.toLowerCase()}-preview.png`)}>Download preview</button></div>
          <details><summary>Generated prompt</summary><p>{result.prompt}</p></details>
        </>}
      </div>
    </section>
  </main>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
