import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from 'react-oidc-context'
import './index.css'
import App from './App.jsx'
import { oidcConfig } from './auth.config.js'
import { initRippleEffect } from './rippleEffect.js'
import { ThemeProvider } from './ThemeContext.jsx'

initRippleEffect();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider {...oidcConfig}>
        <App />
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>
)