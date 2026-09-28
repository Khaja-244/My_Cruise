import React from 'react';import {Navigate} from 'react-router-dom';import {useAuth} from '../context/AuthContext';
export default function PartnerRoute({children}){const {user,loading}=useAuth();if(loading)return <div className="p-8">Loading…</div>;return user?.role==='partner'?children:<Navigate to="/login" replace/>}
