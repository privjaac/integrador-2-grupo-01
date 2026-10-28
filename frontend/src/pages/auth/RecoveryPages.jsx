import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { requestPasswordRecovery, resetPassword } from "../../api/auth";

const panel = { maxWidth: 420, margin: "10vh auto", padding: 28, color: "#e8edf5", background: "#101426", border: "1px solid rgba(63,229,229,.25)", borderRadius: 12, fontFamily: "Arial, sans-serif" };
const input = { display: "block", boxSizing: "border-box", width: "100%", margin: "8px 0 18px", padding: 12, color: "white", background: "#090d19", border: "1px solid #48516a", borderRadius: 6 };

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try { await requestPasswordRecovery(email); setSent(true); }
    catch { setError("No se pudo procesar la solicitud. Reintenta más tarde."); }
    finally { setBusy(false); }
  };
  return <main style={panel}><h1>Recuperar acceso</h1><p>Ingresa el correo registrado. Si corresponde a una cuenta activa, recibirás instrucciones.</p>
    {sent ? <p role="status">Si el correo corresponde a una cuenta activa, recibirás instrucciones para recuperar el acceso.</p> : <form onSubmit={submit}>
      <label htmlFor="recovery-email">Correo electrónico</label><input id="recovery-email" style={input} type="email" maxLength={150} autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      {error && <p role="alert">{error}</p>}<button disabled={busy}>{busy ? "Enviando…" : "Enviar instrucciones"}</button>
    </form>}
    <p><Link to="/login">Volver al inicio de sesión</Link></p>
  </main>;
}

export function ResetPasswordPage() {
  const { token } = useParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault(); setError("");
    if (password.length < 6 || password.length > 50) { setError("La contraseña debe tener entre 6 y 50 caracteres."); return; }
    if (password !== confirm) { setError("Las contraseñas no coinciden."); return; }
    setBusy(true);
    try { await resetPassword(token, password, confirm); setComplete(true); }
    catch { setError("El enlace no es válido o venció. Solicita uno nuevo."); }
    finally { setBusy(false); }
  };
  return <main style={panel}><h1>Nueva contraseña</h1>
    {complete ? <p role="status">Contraseña actualizada. <Link to="/login">Iniciar sesión</Link></p> : <form onSubmit={submit}>
      <label htmlFor="new-password">Contraseña (6 a 50 caracteres)</label><input id="new-password" style={input} type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      <label htmlFor="confirm-password">Confirmar contraseña</label><input id="confirm-password" style={input} type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      {error && <p role="alert">{error}</p>}<button disabled={busy}>{busy ? "Actualizando…" : "Actualizar contraseña"}</button>
    </form>}
    <p><Link to="/login">Volver al inicio de sesión</Link></p>
  </main>;
}
