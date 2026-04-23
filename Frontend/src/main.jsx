import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import SecondBrainApp from './SecondBrainApp.jsx'
import './secondbrain.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <SecondBrainApp />
  </StrictMode>,
)
