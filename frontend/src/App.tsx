import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { WorkspacePage } from '@/pages/WorkspacePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/workspace/:projectId?" element={<WorkspacePage />} />
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
