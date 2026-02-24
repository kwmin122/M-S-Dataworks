import React from 'react';
import { motion } from 'framer-motion';
import { staggerItem } from '../../utils/animations';
import type { LucideIcon } from 'lucide-react';

interface SummaryCardProps {
  icon: LucideIcon;
  label: string;
  value: number | string;
  color: string; // tailwind text color class, e.g. 'text-kira-600'
  bgColor: string; // tailwind bg class, e.g. 'bg-kira-50'
  actionLabel?: string;
  onAction?: () => void;
}

const SummaryCard: React.FC<SummaryCardProps> = ({ icon: Icon, label, value, color, bgColor, actionLabel, onAction }) => (
  <motion.div
    variants={staggerItem}
    className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
  >
    <div className="flex items-center gap-3 mb-3">
      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${bgColor}`}>
        <Icon size={20} className={color} />
      </div>
      <p className="text-sm font-medium text-slate-500">{label}</p>
    </div>
    <p className="text-3xl font-bold text-slate-900">{value}</p>
    {actionLabel && onAction && (
      <button
        type="button"
        onClick={onAction}
        className={`mt-3 text-sm font-medium ${color} hover:underline`}
      >
        {actionLabel} →
      </button>
    )}
  </motion.div>
);

export default SummaryCard;
