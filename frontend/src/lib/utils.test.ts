import { fmtINR, hasRole, isActive } from './utils'

test('role hierarchy', () => {
  expect(hasRole('admin', 'operator')).toBe(true)
  expect(hasRole('viewer', 'operator')).toBe(false)
  expect(hasRole(null, 'viewer')).toBe(false)
})
test('formatting', () => {
  expect(fmtINR(485000)).toBe('₹4,85,000')
  expect(isActive('WAITING_FOR_APPROVAL')).toBe(true)
  expect(isActive('COMPLETED')).toBe(false)
})
