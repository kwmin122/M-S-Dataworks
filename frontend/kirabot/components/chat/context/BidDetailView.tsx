import React from 'react';
import { Calendar, MapPin, ExternalLink } from 'lucide-react';
import type { BidNotice } from '../../../types';

interface Props {
  bid: BidNotice;
}

const BidDetailView: React.FC<Props> = ({ bid }) => {
  return (
    <div className="p-4 space-y-4">
      <h3 className="text-base font-bold text-slate-800 leading-snug">{bid.title}</h3>

      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <MapPin size={14} className="shrink-0 text-slate-400" />
          <span>{bid.region || '지역 정보 없음'}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Calendar size={14} className="shrink-0 text-slate-400" />
          <span>마감: {bid.deadlineAt ? bid.deadlineAt.slice(0, 10) : '미정'}</span>
        </div>
      </div>

      {bid.url && (
        <a
          href={bid.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-primary-600 hover:bg-slate-50"
        >
          <ExternalLink size={14} /> 공고 원문 보기
        </a>
      )}

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs text-slate-500">공고 ID</p>
        <p className="text-sm font-mono text-slate-700">{bid.id}</p>
      </div>
    </div>
  );
};

export default BidDetailView;
