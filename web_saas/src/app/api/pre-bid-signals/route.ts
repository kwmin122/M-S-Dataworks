import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const region = searchParams.get('region');

  const signals = await prisma.preBidSignal.findMany({
    where: region ? { region: { contains: region, mode: 'insensitive' } } : {},
    orderBy: { createdAt: 'desc' },
    take: 50,
  });

  return NextResponse.json({ signals });
}
