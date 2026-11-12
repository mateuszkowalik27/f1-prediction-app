import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest nie ma domyślnie globalnego afterEach, więc RTL nie sprząta sam po każdym teście.
afterEach(() => cleanup())
