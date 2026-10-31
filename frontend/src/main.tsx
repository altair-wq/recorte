import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import { LangProvider } from './hooks/useLang'
import Home from './pages/Home'
import Workspace from './pages/Workspace'
import Export from './pages/Export'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LangProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/s/:sourceId" element={<Workspace />} />
          <Route path="/c/:clipId" element={<Export />} />
        </Routes>
      </BrowserRouter>
    </LangProvider>
  </StrictMode>,
)
