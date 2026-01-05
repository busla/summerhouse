/**
 * PaymentStatusBadge Component
 *
 * Displays payment/transaction status with appropriate colors and icons.
 * Supports both TransactionStatus (from Payment model) and PaymentStatus types.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-008 (Status Display)
 */

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  Clock,
  CheckCircle,
  XCircle,
  RefreshCw,
  AlertCircle,
  Ban,
} from 'lucide-react'
import type { TransactionStatus, PaymentStatus } from '@/lib/api-client'

// Union type to accept both status types
type Status = TransactionStatus | PaymentStatus

interface PaymentStatusBadgeProps {
  /** Payment or transaction status */
  status: Status
  /** Show icon alongside text */
  showIcon?: boolean
  /** Additional CSS classes */
  className?: string
}

/** Status configuration with colors, icons, and labels */
const STATUS_CONFIG: Record<
  Status,
  {
    label: string
    icon: React.ComponentType<{ className?: string }>
    variant: 'success' | 'warning' | 'destructive' | 'info' | 'default'
  }
> = {
  pending: {
    label: 'Pending',
    icon: Clock,
    variant: 'warning',
  },
  paid: {
    label: 'Paid',
    icon: CheckCircle,
    variant: 'success',
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle,
    variant: 'success',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    variant: 'destructive',
  },
  refunded: {
    label: 'Refunded',
    icon: RefreshCw,
    variant: 'info',
  },
  partial_refund: {
    label: 'Partial Refund',
    icon: RefreshCw,
    variant: 'info',
  },
  cancelled: {
    label: 'Cancelled',
    icon: Ban,
    variant: 'default',
  },
}

/** Variant-specific Tailwind classes */
const VARIANT_STYLES: Record<string, string> = {
  success: 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800',
  warning: 'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800',
  destructive: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
  info: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800',
  default: 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700',
}

export function PaymentStatusBadge({
  status,
  showIcon = true,
  className,
}: PaymentStatusBadgeProps) {
  const config = STATUS_CONFIG[status]

  if (!config) {
    // Fallback for unknown status
    return (
      <Badge variant="outline" className={cn('gap-1', className)}>
        <AlertCircle className="h-3 w-3" />
        {status}
      </Badge>
    )
  }

  const Icon = config.icon
  const variantStyle = VARIANT_STYLES[config.variant]

  return (
    <Badge
      variant="outline"
      className={cn('gap-1.5', variantStyle, className)}
    >
      {showIcon && <Icon className="h-3 w-3" />}
      {config.label}
    </Badge>
  )
}
