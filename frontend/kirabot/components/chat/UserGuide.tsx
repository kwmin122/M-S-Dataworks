import React from 'react';
import { ArrowLeft, Play, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useActiveConversation } from '../../hooks/useActiveConversation';

interface UserGuideProps {
  onClose: () => void;
  onStartCompanyDB?: () => void;
}

interface Capability {
  emoji: string;
  name: string;
  description: string;
  howLabel: string;
  howColor: string;
  howBg: string;
  iconBg: string;
  instructions: string[];
}

const capabilities: Capability[] = [
  {
    emoji: '\uD83C\uDFE2',
    name: '\uD68C\uC0AC \uC5ED\uB7C9 DB \uAD6C\uCD95',
    description: '\uBAA8\uB4E0 \uAE30\uB2A5\uC758 \uD488\uC9C8\uC744 \uACB0\uC815\uD558\uB294 \uD575\uC2EC \uB2E8\uACC4\uC785\uB2C8\uB2E4. \uD68C\uC0AC \uC815\uBCF4\uAC00 \uC5C6\uC73C\uBA74 \uBC94\uC6A9 \uBB38\uC11C\uB9CC \uC0DD\uC131\uB418\uACE0, \uD68C\uC0AC \uC815\uBCF4\uAC00 \uC788\uC73C\uBA74 \uC6B0\uB9AC \uD68C\uC0AC\uC5D0 \uB531 \uB9DE\uB294 \uB9DE\uCDA4\uD615 \uBB38\uC11C\uAC00 \uC0DD\uC131\uB429\uB2C8\uB2E4.',
    howLabel: '\uAC00\uC7A5 \uBA3C\uC800 \uD574\uC8FC\uC138\uC694',
    howColor: 'text-amber-600',
    howBg: 'bg-amber-50',
    iconBg: 'bg-amber-50',
    instructions: [
      "\uCC44\uD305 \uC2DC\uC791 \uD654\uBA74\uC5D0\uC11C '\uD68C\uC0AC \uC5ED\uB7C9 DB \uAD6C\uCD95' \uBC84\uD2BC\uC744 \uD074\uB9AD\uD558\uC138\uC694.",
      '\uD68C\uC0AC\uC18C\uAC1C\uC11C, \uC2E4\uC801\uC99D\uBA85\uC11C, \uC778\uB825\uD604\uD669, \uACFC\uAC70 \uC81C\uC548\uC11C \uB4F1\uC744 \uC5C5\uB85C\uB4DC\uD569\uB2C8\uB2E4.',
      'AI\uAC00 \uC790\uB3D9\uC73C\uB85C \uBD84\uC11D\xB7\uC815\uB9AC\uD558\uC5EC \uC774\uD6C4 \uBAA8\uB4E0 \uBB38\uC11C(\uC81C\uC548\uC11C, WBS, PPT, \uC2E4\uC801\uAE30\uC220\uC11C)\uC5D0 \uBC18\uC601\uD569\uB2C8\uB2E4.',
    ],
  },
  {
    emoji: '\uD83D\uDD0D',
    name: '\uACF5\uACE0 \uAC80\uC0C9',
    description: '\uB098\uB77C\uC7A5\uD130\uC5D0\uC11C \uD0A4\uC6CC\uB4DC\uB85C \uC785\uCC30 \uACF5\uACE0\uB97C \uCC3E\uC544\uC90D\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-blue-500',
    howBg: 'bg-blue-50',
    iconBg: 'bg-blue-50',
    instructions: [
      '\uCC44\uD305\uCC3D\uC5D0 \uCC3E\uACE0 \uC2F6\uC740 \uD0A4\uC6CC\uB4DC\uB97C \uC785\uB825\uD558\uC138\uC694.',
      '\uC608: "AI \uC18C\uD504\uD2B8\uC6E8\uC5B4 \uACF5\uACE0 \uAC80\uC0C9\uD574\uC918"',
    ],
  },
  {
    emoji: '\uD83D\uDCCB',
    name: 'RFP \uBD84\uC11D',
    description: '\uACF5\uACE0 \uBB38\uC11C\uC5D0\uC11C \uC790\uACA9\uC694\uAC74\uC744 \uCD94\uCD9C\uD558\uACE0 \uD575\uC2EC \uB0B4\uC6A9\uC744 \uC694\uC57D\uD569\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-orange-500',
    howBg: 'bg-orange-50',
    iconBg: 'bg-orange-50',
    instructions: [
      '\uBC29\uBC95 1: \uAC80\uC0C9 \uACB0\uACFC\uC5D0\uC11C \uACF5\uACE0\uB97C \uD074\uB9AD \u2014 \uCCA8\uBD80\uD30C\uC77C\uC774 \uC790\uB3D9 \uBD84\uC11D\uB429\uB2C8\uB2E4.',
      '\uBC29\uBC95 2: \uD074\uB9BD \uBC84\uD2BC\uC73C\uB85C PDF/HWP \uD30C\uC77C\uC744 \uC9C1\uC811 \uC5C5\uB85C\uB4DC\uD558\uC138\uC694.',
    ],
  },
  {
    emoji: '\u2705',
    name: 'GO/NO-GO \uC790\uB3D9 \uD310\uB2E8',
    description: '\uD68C\uC0AC \uC790\uACA9\uC694\uAC74\uACFC \uACF5\uACE0 \uC694\uAC74\uC744 AI\uAC00 \uC790\uB3D9 \uBE44\uAD50\uD569\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-emerald-500',
    howBg: 'bg-emerald-50',
    iconBg: 'bg-emerald-50',
    instructions: [
      "\uBA3C\uC800 '\uD68C\uC0AC \uC5ED\uB7C9 DB'\uC5D0 \uC2E4\uC801\xB7\uC778\uB825 \uC815\uBCF4\uB97C \uB4F1\uB85D\uD558\uC138\uC694.",
      '\uACF5\uACE0\uB97C \uBD84\uC11D\uD558\uBA74 GO/NO-GO \uACB0\uACFC\uAC00 \uC790\uB3D9\uC73C\uB85C \uD45C\uC2DC\uB429\uB2C8\uB2E4.',
      '\uC694\uAC74\uBCC4 \uCDA9\uC871 \uC5EC\uBD80\uB97C \uD55C\uB208\uC5D0 \uD655\uC778\uD560 \uC218 \uC788\uC5B4\uC694.',
    ],
  },
  {
    emoji: '\uD83D\uDCDD',
    name: '\uC81C\uC548\uC11C DOCX \uC0DD\uC131',
    description: 'RFP \uBD84\uC11D \uACB0\uACFC + \uD68C\uC0AC \uC5ED\uB7C9\uC744 \uAE30\uBC18\uC73C\uB85C \uB9DE\uCDA4 \uC81C\uC548\uC11C\uB97C \uC0DD\uC131\uD569\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-blue-600',
    howBg: 'bg-blue-50',
    iconBg: 'bg-blue-50',
    instructions: [
      "\uACF5\uACE0 \uBD84\uC11D\uC774 \uC644\uB8CC\uB418\uBA74 '\uC81C\uC548\uC11C v2 \uC0DD\uC131' \uBC84\uD2BC\uC774 \uB098\uD0C0\uB0A9\uB2C8\uB2E4.",
      '\uD074\uB9AD\uD558\uBA74 AI\uAC00 \uC139\uC158\uBCC4 \uC81C\uC548\uC11C\uB97C \uC790\uB3D9 \uC791\uC131\uD569\uB2C8\uB2E4.',
      '\uC644\uC131\uB41C DOCX \uD30C\uC77C\uC744 \uB2E4\uC6B4\uB85C\uB4DC\uD558\uC5EC \uC218\uC815\xB7\uC81C\uCD9C\uD558\uC138\uC694.',
    ],
  },
  {
    emoji: '\uD83D\uDCCA',
    name: 'WBS \xB7 PPT \xB7 \uC2E4\uC801\uAE30\uC220\uC11C',
    description: '\uC218\uD589\uACC4\uD68D\uC11C, \uBC1C\uD45C\uC790\uB8CC, \uC2E4\uC801\uAE30\uC220\uC11C\uB97C \uD55C \uBC88\uC5D0 \uB9CC\uB4E4\uC5B4\uC90D\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-purple-500',
    howBg: 'bg-purple-50',
    iconBg: 'bg-purple-50',
    instructions: [
      '\uACF5\uACE0 \uBD84\uC11D \uC644\uB8CC \uD6C4 \uAC01 \uBC84\uD2BC\uC774 \uD65C\uC131\uD654\uB429\uB2C8\uB2E4.',
      "'WBS \uC0DD\uC131' \u2192 \uC218\uD589\uACC4\uD68D\uC11C(DOCX) + \uC5D1\uC140(XLSX) + \uAC04\uD2B8\uCC28\uD2B8(PNG)",
      "'PPT \uC0DD\uC131' \u2192 \uBC1C\uD45C\uC790\uB8CC(PPTX) + \uC608\uC0C1\uC9C8\uBB38 10\uAC1C",
      "'\uC2E4\uC801\uAE30\uC220\uC11C' \u2192 \uD68C\uC0AC DB \uAE30\uBC18 \uB9DE\uCDA4 \uAE30\uC220\uC11C(DOCX)",
    ],
  },
  {
    emoji: '\u270F\uFE0F',
    name: '\uC81C\uC548\uC11C \uC9C1\uC811 \uC218\uC815 & AI \uD559\uC2B5',
    description: 'AI\uAC00 \uC0DD\uC131\uD55C \uC81C\uC548\uC11C\uB97C \uC139\uC158\uBCC4\uB85C \uC218\uC815\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4. \uC218\uC815 \uB0B4\uC6A9\uC740 AI\uAC00 \uD559\uC2B5\uD558\uC5EC \uB2E4\uC74C \uC0DD\uC131 \uC2DC \uC790\uB3D9 \uBC18\uC601\uB429\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-teal-500',
    howBg: 'bg-teal-50',
    iconBg: 'bg-teal-50',
    instructions: [
      "\uC0C1\uB2E8 '\uBB38\uC11C \uAD00\uB9AC' \u2192 '\uC81C\uC548\uC11C' \uD0ED\uC5D0\uC11C \uC139\uC158\uBCC4 \uB0B4\uC6A9\uC744 \uD655\uC778\uD569\uB2C8\uB2E4.",
      '\uAC01 \uC139\uC158\uC744 \uC9C1\uC811 \uD3B8\uC9D1\uD558\uACE0 \uC800\uC7A5\uD558\uC138\uC694.',
      "'DOCX \uC7AC\uC0DD\uC131' \uBC84\uD2BC\uC73C\uB85C \uC218\uC815\uB41C \uB0B4\uC6A9\uC73C\uB85C \uC0C8 \uBB38\uC11C\uB97C \uB9CC\uB4ED\uB2C8\uB2E4.",
      '\uC218\uC815\uC744 3\uD68C \uC774\uC0C1 \uBC18\uBCF5\uD558\uBA74 AI\uAC00 \uD328\uD134\uC744 \uD559\uC2B5\uD558\uC5EC \uB2E4\uC74C\uBD80\uD130 \uC790\uB3D9 \uBC18\uC601\uD569\uB2C8\uB2E4.',
    ],
  },
  {
    emoji: '\u2705',
    name: '\uC81C\uCD9C \uCCB4\uD06C\uB9AC\uC2A4\uD2B8',
    description: 'RFP\uC5D0\uC11C \uD544\uC218/\uC120\uD0DD \uC81C\uCD9C\uC11C\uB958\uB97C \uC790\uB3D9 \uCD94\uCD9C\uD558\uC5EC \uB204\uB77D\uC744 \uBC29\uC9C0\uD569\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-cyan-500',
    howBg: 'bg-cyan-50',
    iconBg: 'bg-cyan-50',
    instructions: [
      "\uACF5\uACE0 \uBD84\uC11D \uC644\uB8CC \uD6C4 '\uCCB4\uD06C\uB9AC\uC2A4\uD2B8' \uBC84\uD2BC\uC744 \uD074\uB9AD\uD558\uC138\uC694.",
      '\uD544\uC218 \uC81C\uCD9C\uC11C\uB958\uC640 \uC120\uD0DD \uC81C\uCD9C\uC11C\uB958\uAC00 \uBD84\uB9AC\uB418\uC5B4 \uD45C\uC2DC\uB429\uB2C8\uB2E4.',
      '\uC785\uCC30 \uC81C\uCD9C \uC804 \uBE60\uC9C4 \uC11C\uB958\uAC00 \uC5C6\uB294\uC9C0 \uD655\uC778\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
    ],
  },
  {
    emoji: '\uD83D\uDCAC',
    name: '\uBB38\uC11C \uAE30\uBC18 Q&A',
    description: '\uBD84\uC11D\uB41C \uBB38\uC11C\uC5D0 \uB300\uD574 \uC790\uC720\uB86D\uAC8C \uC9C8\uBB38\uD558\uBA74 AI\uAC00 \uB2F5\uBCC0\uD569\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-indigo-500',
    howBg: 'bg-indigo-50',
    iconBg: 'bg-indigo-50',
    instructions: [
      '\uACF5\uACE0 \uBD84\uC11D\uC774 \uC644\uB8CC\uB418\uBA74 \uC790\uB3D9\uC73C\uB85C Q&A \uBAA8\uB4DC\uB85C \uC804\uD658\uB429\uB2C8\uB2E4.',
      '\uCC44\uD305\uCC3D\uC5D0 \uAD81\uAE08\uD55C \uC810\uC744 \uC790\uC720\uB86D\uAC8C \uC785\uB825\uD558\uC138\uC694.',
      '\uC608: "\uC774 \uACF5\uACE0\uC758 \uD3C9\uAC00 \uBC30\uC810 \uAE30\uC900\uC774 \uBB50\uC57C?", "\uC0AC\uC5C5\uBE44 \uC81C\uD55C\uC774 \uC788\uC5B4?"',
    ],
  },
  {
    emoji: '\uD83D\uDCE6',
    name: '\uC77C\uAD04 \uD3C9\uAC00 & CSV \uB0B4\uBCF4\uB0B4\uAE30',
    description: '\uC5EC\uB7EC \uACF5\uACE0\uB97C \uD55C \uBC88\uC5D0 GO/NO-GO \uD3C9\uAC00\uD558\uACE0, \uAC80\uC0C9 \uACB0\uACFC\uB97C CSV\uB85C \uB0B4\uB824\uBC1B\uC744 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-sky-500',
    howBg: 'bg-sky-50',
    iconBg: 'bg-sky-50',
    instructions: [
      '\uACF5\uACE0 \uAC80\uC0C9 \uACB0\uACFC\uC5D0\uC11C \uC6D0\uD558\uB294 \uACF5\uACE0\uB4E4\uC744 \uCCB4\uD06C\uD558\uC138\uC694.',
      "'\uC77C\uAD04 \uD3C9\uAC00' \uBC84\uD2BC\uC744 \uB204\uB974\uBA74 \uC120\uD0DD\uD55C \uACF5\uACE0\uB4E4\uC744 \uB3D9\uC2DC\uC5D0 GO/NO-GO \uD310\uB2E8\uD569\uB2C8\uB2E4.",
      "'CSV' \uBC84\uD2BC\uC73C\uB85C \uAC80\uC0C9 \uACB0\uACFC\uB97C \uC5D1\uC140 \uD30C\uC77C\uB85C \uB0B4\uB824\uBC1B\uC744 \uC218 \uC788\uC2B5\uB2C8\uB2E4.",
    ],
  },
  {
    emoji: '\uD83D\uDD14',
    name: '\uC54C\uB9BC \uC124\uC815',
    description: '\uAD00\uC2EC \uBD84\uC57C\uC758 \uC0C8 \uACF5\uACE0\uAC00 \uB4F1\uB85D\uB418\uBA74 \uC774\uBA54\uC77C\uB85C \uC54C\uB824\uB4DC\uB9BD\uB2C8\uB2E4.',
    howLabel: '\uC774\uB807\uAC8C \uD558\uC138\uC694',
    howColor: 'text-rose-500',
    howBg: 'bg-rose-50',
    iconBg: 'bg-rose-50',
    instructions: [
      "\uC0AC\uC774\uB4DC\uBC14 \uD558\uB2E8\uC758 '\uC54C\uB9BC \uC124\uC815' \uBA54\uB274\uB97C \uD074\uB9AD\uD558\uC138\uC694.",
      '\uAD00\uC2EC \uD0A4\uC6CC\uB4DC, \uC5C5\uBB34\uAD6C\uBD84, \uC9C0\uC5ED, \uAE08\uC561 \uBC94\uC704 \uB4F1\uC744 \uC124\uC815\uD569\uB2C8\uB2E4.',
      '\uC870\uAC74\uC5D0 \uB9DE\uB294 \uC0C8 \uACF5\uACE0\uAC00 \uB098\uC624\uBA74 \uC790\uB3D9\uC73C\uB85C \uC774\uBA54\uC77C \uC54C\uB9BC\uC744 \uBC1B\uC2B5\uB2C8\uB2E4.',
    ],
  },
];

const UserGuide: React.FC<UserGuideProps> = ({ onClose, onStartCompanyDB }) => {
  const { conversation } = useActiveConversation();
  const hasCompanyProfile = Boolean(conversation?.companyProfile?.companyName);
  const companyChunks = conversation?.companyChunks || 0;

  return (
    <div className="flex h-full flex-col bg-[#FAFBFC]">
      {/* Header */}
      <div className="flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-sm">
        <button
          type="button"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          title="\uCC44\uD305\uC73C\uB85C \uB3CC\uC544\uAC00\uAE30"
        >
          <ArrowLeft size={18} />
        </button>
        <h2 className="text-sm font-bold text-slate-800">\uC0AC\uC6A9 \uAC00\uC774\uB4DC</h2>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[760px] px-6 py-12">
          {/* Hero */}
          <div className="mb-10 text-center">
            <h1 className="mb-3 text-[32px] font-extrabold leading-tight text-slate-900 font-title">
              Kira Bot\uC774 \uD560 \uC218 \uC788\uB294 \uAC83\uB4E4
            </h1>
            <p className="text-base leading-relaxed text-slate-500">
              \uAC01 \uAE30\uB2A5\uC740 \uB3C5\uB9BD\uC801\uC73C\uB85C \uC0AC\uC6A9\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.<br />
              \uD544\uC694\uD55C \uAC83\uBD80\uD130 \uC2DC\uC791\uD558\uC138\uC694.
            </p>
          </div>

          {/* Company Status Card */}
          {hasCompanyProfile ? (
            <div className="mb-8 rounded-xl border border-green-200 bg-green-50 p-5">
              <div className="flex items-start gap-3">
                <CheckCircle2 size={22} className="mt-0.5 shrink-0 text-green-600" />
                <div>
                  <p className="text-sm font-semibold text-green-900">
                    {conversation.companyProfile.companyName} \u2014 {companyChunks}\uAC1C \uBB38\uC11C \uB4F1\uB85D\uB428
                  </p>
                  <p className="mt-1 text-sm text-green-700">
                    GO/NO-GO \uC790\uB3D9 \uD310\uB2E8\uACFC \uB9DE\uCDA4\uD615 \uC81C\uC548\uC11C \uC0DD\uC131\uC774 \uAC00\uB2A5\uD569\uB2C8\uB2E4.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="mb-8 rounded-xl border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-orange-50 p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100">
                  <AlertCircle size={20} className="text-amber-600" />
                </div>
                <div className="flex-1">
                  <p className="text-base font-bold text-amber-900">
                    \uD68C\uC0AC \uBB38\uC11C\uB97C \uBA3C\uC800 \uB4F1\uB85D\uD574\uC8FC\uC138\uC694!
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-amber-800">
                    \uD68C\uC0AC\uC18C\uAC1C\uC11C, \uC2E4\uC801\uC99D\uBA85\uC11C, \uC778\uB825\uD604\uD669\uC744 \uB4F1\uB85D\uD558\uBA74<br />
                    <strong>GO/NO-GO \uD310\uB2E8 \uC815\uD655\uB3C4\uAC00 2\uBC30 \uC774\uC0C1 \uD5A5\uC0C1</strong>\uB418\uACE0,<br />
                    \uC81C\uC548\uC11C\xB7WBS\xB7PPT \uBAA8\uB450 <strong>\uC6B0\uB9AC \uD68C\uC0AC\uC5D0 \uB531 \uB9DE\uB294 \uB9DE\uCDA4\uD615</strong>\uC73C\uB85C \uC0DD\uC131\uB429\uB2C8\uB2E4.
                  </p>
                  <button
                    type="button"
                    onClick={() => { onClose(); onStartCompanyDB?.(); }}
                    className="mt-3 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 transition-colors"
                  >
                    \uD68C\uC0AC \uC5ED\uB7C9 DB \uAD6C\uCD95 \uC2DC\uC791\uD558\uAE30
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Capability Cards */}
          <div className="space-y-5">
            {capabilities.map((cap, idx) => (
              <div
                key={cap.name}
                className={`rounded-2xl border p-7 shadow-sm ${
                  idx === 0
                    ? 'border-amber-200 bg-gradient-to-br from-white to-amber-50/50 ring-1 ring-amber-100'
                    : 'border-slate-200 bg-white'
                }`}
              >
                {/* Top: icon + name + description */}
                <div className="flex items-start gap-4">
                  <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] ${cap.iconBg}`}>
                    <span className="text-[22px]">{cap.emoji}</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-bold text-slate-900 font-title">{cap.name}</h3>
                      {idx === 0 && (
                        <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">
                          추천
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-slate-500">{cap.description}</p>
                  </div>
                </div>

                {/* Divider */}
                <div className="my-5 h-px bg-slate-100" />

                {/* How-to */}
                <div>
                  <p className={`mb-2.5 text-xs font-bold uppercase tracking-wider ${cap.howColor}`}>
                    {cap.howLabel}
                  </p>
                  <div className="space-y-1.5">
                    {cap.instructions.map((instruction, i) => (
                      <p key={i} className="text-sm leading-relaxed text-slate-600">
                        {cap.instructions.length > 1 ? `${i + 1}. ${instruction}` : instruction}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* CTA */}
          <div className="mt-10 rounded-2xl bg-kira-600 p-8 text-center text-white shadow-xl">
            <h3 className="mb-3 text-2xl font-extrabold font-title">\uC9C0\uAE08 \uBC14\uB85C \uC2DC\uC791\uD558\uC138\uC694</h3>
            <p className="mb-6 leading-relaxed text-blue-100">
              \uACF5\uACE0 \uAC80\uC0C9\uBD80\uD130 \uC81C\uC548\uC11C \uC0DD\uC131\uAE4C\uC9C0,<br />
              Kira Bot\uC774 \uC785\uCC30\uC758 \uBAA8\uB4E0 \uACFC\uC815\uC744 \uB3C4\uC640\uB4DC\uB9BD\uB2C8\uB2E4.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-base font-bold text-kira-700 hover:bg-kira-50 transition-colors shadow-lg"
            >
              <Play size={18} />
              \uCC44\uD305 \uC2DC\uC791\uD558\uAE30
            </button>
          </div>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-xs text-slate-400">Kira Bot v2.0 | MS Solutions</p>
            <p className="text-xs text-slate-300 mt-1">\uACF5\uACF5\uC870\uB2EC \uC785\uCC30 AI \uC790\uB3D9\uD654 \uD50C\uB7AB\uD3FC</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserGuide;
