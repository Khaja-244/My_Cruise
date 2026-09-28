import PageHero from '../../components/ui/PageHero';
import {useState} from "react";
import {useNavigate,useSearchParams} from "react-router-dom";
import {api} from "../../api/client";

export default function ResetPassword(){
 const [params]=useSearchParams(); const nav=useNavigate();
 const [password,setPassword]=useState(""); const [confirm,setConfirm]=useState(""); const [msg,setMsg]=useState(""); const [error,setError]=useState("");
 const token=params.get("token")||"";
 const submit=async e=>{e.preventDefault();setError("");setMsg(""); if(password!==confirm){setError("Passwords do not match.");return;} try{await api.post("/auth/reset-password",{reset_token:token,new_password:password});setMsg("Password reset successfully. You can now sign in.");setTimeout(()=>nav("/login"),1000);}catch(x){setError(x.response?.data?.error?.message||"Unable to reset password.");}};
 return <div><PageHero eyebrow="Account recovery" title="Choose a new password" subtitle="Set a new password and return to your secure my_cruise account." /><div className="container-app py-10 lg:py-14"><div className="max-w-md mx-auto"><div className="card p-8"><h1 className="text-3xl font-bold">Choose a new password</h1>{error&&<p className="text-error mt-3">{error}</p>}{msg&&<p className="text-success mt-3">{msg}</p>}<form className="space-y-4 mt-7" onSubmit={submit}><input className="input" type="password" minLength="8" placeholder="New password" value={password} onChange={e=>setPassword(e.target.value)} required/><input className="input" type="password" minLength="8" placeholder="Confirm password" value={confirm} onChange={e=>setConfirm(e.target.value)} required/><button className="btn btn-primary w-full" disabled={!token}>Reset password</button></form></div></div></div></div>;
}
