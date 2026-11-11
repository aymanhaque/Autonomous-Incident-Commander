import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ConsolePage from './pages/ConsolePage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/approvals/:id" element={<ConsolePage />} />
        <Route path="/approvals" element={<ConsolePage />} />
        <Route path="*" element={<Navigate to="/approvals" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
