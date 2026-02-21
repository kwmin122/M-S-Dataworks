import { NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? 'sk_test_placeholder');
const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET ?? '';

// Stripe SDK v20 removed current_period_start/end from the TS type,
// but the fields still exist in the live webhook payload.
interface SubscriptionWithPeriod extends Stripe.Subscription {
  current_period_start: number;
  current_period_end: number;
}

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const sig = req.headers.get('stripe-signature') ?? '';

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(rawBody, sig, webhookSecret);
  } catch (_e) {
    return NextResponse.json({ error: 'invalid_signature' }, { status: 400 });
  }

  switch (event.type) {
    case 'customer.subscription.created':
    case 'customer.subscription.updated': {
      const sub = event.data.object as SubscriptionWithPeriod;
      const orgId = sub.metadata?.organizationId;
      if (!orgId) break;

      const plan = sub.items.data[0]?.price?.nickname === 'PRO' ? 'PRO' : 'FREE';
      const status = sub.status.toUpperCase();

      await prisma.subscription.upsert({
        where: { organizationId: orgId },
        create: {
          id: createId(),
          organizationId: orgId,
          plan: plan as 'FREE' | 'PRO',
          status,
          stripeSubId: sub.id,
          currentPeriodStart: new Date(sub.current_period_start * 1000),
          currentPeriodEnd: new Date(sub.current_period_end * 1000),
        },
        update: {
          plan: plan as 'FREE' | 'PRO',
          status,
          stripeSubId: sub.id,
          currentPeriodStart: new Date(sub.current_period_start * 1000),
          currentPeriodEnd: new Date(sub.current_period_end * 1000),
        },
      });
      break;
    }

    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription;
      const orgId = sub.metadata?.organizationId;
      if (!orgId) break;
      await prisma.subscription.updateMany({
        where: { organizationId: orgId },
        data: { status: 'CANCELED' },
      });
      break;
    }
  }

  return NextResponse.json({ received: true });
}
