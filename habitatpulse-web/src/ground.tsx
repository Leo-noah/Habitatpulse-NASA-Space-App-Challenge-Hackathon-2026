import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import GroundDashboard from './components/GroundDashboard'
import GroundLogin from './components/GroundLogin'

function GroundApp() {
  const [signedIn, setSignedIn] = useState(false)

  return signedIn
    ? <GroundDashboard onSignOut={() => setSignedIn(false)} />
    : <GroundLogin onSignIn={() => setSignedIn(true)} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GroundApp />
  </StrictMode>,
)
