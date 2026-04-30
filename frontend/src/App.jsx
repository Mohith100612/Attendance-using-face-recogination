import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import AttendancePage from './pages/AttendancePage'
import RegisterPage from './pages/RegisterPage'

export default function App() {
  return (
    <BrowserRouter>
      <nav className="nav">
        <span className="nav-brand">FaceAttend</span>
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Attendance
          </NavLink>
          <NavLink to="/spotregister" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Spotregister
          </NavLink>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<AttendancePage />} />
        <Route path="/spotregister" element={<RegisterPage />} />
      </Routes>
    </BrowserRouter>
  )
}
