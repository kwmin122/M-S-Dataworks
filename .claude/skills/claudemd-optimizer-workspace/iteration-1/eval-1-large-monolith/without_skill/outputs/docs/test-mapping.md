# Test File Mapping

## Frontend (Jest + RTL)
| File | Target |
|------|--------|
| `src/lib/__tests__/auth.test.ts` | `src/lib/auth.ts` |
| `src/lib/__tests__/stripe.test.ts` | `src/lib/stripe.ts` |
| `src/lib/__tests__/redis.test.ts` | `src/lib/redis.ts` |
| `src/components/__tests__/ProductCard.test.tsx` | `ProductCard.tsx` |
| `src/components/__tests__/CartDrawer.test.tsx` | `CartDrawer.tsx` |
| `src/components/__tests__/CheckoutForm.test.tsx` | `CheckoutForm.tsx` |
| `src/hooks/__tests__/useCart.test.ts` | `useCart.ts` |
| `src/hooks/__tests__/useInventory.test.ts` | `useInventory.ts` |
| `src/app/api/__tests__/orders.test.ts` | `orders/route.ts` |
| `src/app/api/__tests__/products.test.ts` | `products/route.ts` |
| `src/app/api/__tests__/webhooks.test.ts` | `webhooks/stripe/route.ts` |

## Frontend (Playwright E2E)
| File | Target |
|------|--------|
| `e2e/checkout.spec.ts` | Full checkout flow |
| `e2e/inventory.spec.ts` | Stock display + real-time updates |
| `e2e/auth.spec.ts` | Login/register/logout |
| `e2e/admin.spec.ts` | Admin dashboard |

## Inventory Service (Go)
| File | Target |
|------|--------|
| `internal/stock/service_test.go` | Stock management |
| `internal/stock/handler_test.go` | HTTP handlers |
| `internal/reservation/service_test.go` | Stock reservation |
| `pkg/grpc/server_test.go` | gRPC endpoints |

## Analytics (Python)
| File | Target |
|------|--------|
| `tests/test_events.py` | Event ingestion |
| `tests/test_metrics.py` | Metric aggregation |
| `tests/test_export.py` | Data export |

## Notification (Node.js)
| File | Target |
|------|--------|
| `src/__tests__/email.test.ts` | Email sending |
| `src/__tests__/push.test.ts` | Push notifications |
| `src/__tests__/templates.test.ts` | Template rendering |
