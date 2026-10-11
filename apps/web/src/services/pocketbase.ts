import PocketBase from 'pocketbase'

const url = import.meta.env.VITE_POCKETBASE_URL || 'http://localhost:8090'
console.log('🔧 PocketBase URL:', url)
const pb = new PocketBase(url)

export default pb
