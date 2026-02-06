import { useState } from 'react'
import './App.css'
import SubComponent from './component/SubComponent'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <SubComponent/>
    </>
  )
}

export default App
