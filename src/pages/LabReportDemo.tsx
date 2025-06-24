import React from "react";
import { motion } from "framer-motion";
import { ArrowLeftIcon, CheckCircleIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";

const LabReportDemo = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white text-black" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* Back to Dashboard Button */}
      <div className="p-6">
        <motion.button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 mb-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <ArrowLeftIcon className="w-4 h-4" />
          Back to Dashboard
        </motion.button>
      </div>

      {/* A4 Document Container */}
      <div className="flex justify-center">
        <motion.div
          className="bg-white"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          style={{
            width: '816px',
            minHeight: '1056px', // A4 height
            paddingLeft: '48px',
            paddingRight: '48px',
            paddingTop: '64px',
            paddingBottom: '64px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
          }}
        >
          {/* Header */}
          <div className="border-b border-blue-600 pb-6 mb-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                  <span className="text-white font-bold text-sm">B</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-blue-600">
                    Baseerah Technologies
                  </h1>
                  <p className="text-gray-600 text-sm">
                    AI-Powered Lab Interpretation
                  </p>
                </div>
              </div>
              <div className="text-right text-sm" style={{ color: '#111827' }}>
                <div className="font-semibold">Patient ID #12847</div>
                <div className="text-gray-600">Date 24 Jun 2025</div>
                <div className="text-gray-600">Generated 7:16 PM</div>
              </div>
            </div>
          </div>

          {/* Patient Demographics */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4" style={{ color: '#111827' }}>
              Patient Demographics
            </h2>
            <div className="grid grid-cols-2 gap-8">
              <div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: '#374151' }}>Name:</span>
                  <span className="ml-2 font-normal">Ahmed Al-Mansouri</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: '#374151' }}>Age:</span>
                  <span className="ml-2 font-normal">45 years</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: '#374151' }}>Gender:</span>
                  <span className="ml-2 font-normal">Male</span>
                </div>
              </div>
              <div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: '#374151' }}>MRN:</span>
                  <span className="ml-2 font-normal">MRN-2024-12847</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: '#374151' }}>Collection Date:</span>
                  <span className="ml-2 font-normal">{new Date().toLocaleDateString()}</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: '#374151' }}>Ordering Physician:</span>
                  <span className="ml-2 font-normal">Dr. Sarah Al-Zahra</span>
                </div>
              </div>
            </div>
          </div>

          {/* Laboratory Results Table */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4" style={{ color: '#111827' }}>
              Laboratory Results
            </h2>
            <table className="w-full border-collapse border border-gray-300">
              <thead>
                <tr style={{ backgroundColor: '#1E3A8A' }}>
                  <th className="border border-gray-300 p-3 text-left font-semibold text-white">
                    Test
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Result
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Range
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Status
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Units
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-gray-300 p-3 font-medium">HbA1c</td>
                  <td className="border border-gray-300 p-3 text-center font-mono">6.2</td>
                  <td className="border border-gray-300 p-3 text-center">4.0 - 5.6</td>
                  <td className="border border-gray-300 p-3 text-center">
                    <span
                      className="px-3 py-1 rounded-full text-white text-sm font-medium"
                      style={{ backgroundColor: '#F59E0B' }}
                    >
                      High
                    </span>
                  </td>
                  <td className="border border-gray-300 p-3 text-center">%</td>
                </tr>
                <tr className="bg-gray-50">
                  <td className="border border-gray-300 p-3 font-medium">LDL Cholesterol</td>
                  <td className="border border-gray-300 p-3 text-center font-mono">160</td>
                  <td className="border border-gray-300 p-3 text-center">&lt; 100</td>
                  <td className="border border-gray-300 p-3 text-center">
                    <span
                      className="px-3 py-1 rounded-full text-white text-sm font-medium"
                      style={{ backgroundColor: '#EF4444' }}
                    >
                      Critical
                    </span>
                  </td>
                  <td className="border border-gray-300 p-3 text-center">mg/dL</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* AI Clinical Interpretation */}
          <div className="mb-8">
            <div
              className="p-6 rounded-lg border-l-4"
              style={{
                borderLeftColor: '#3B82F6',
                backgroundColor: '#F8FAFC'
              }}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold" style={{ color: '#111827' }}>
                  AI Clinical Interpretation
                </h2>
                <div
                  className="px-3 py-1 rounded-full text-white text-sm font-medium"
                  style={{ backgroundColor: '#3B82F6' }}
                >
                  AI Confidence 94%
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="font-bold mb-2" style={{ color: '#111827' }}>Clinical Summary</h3>
                  <p className="text-gray-700 leading-relaxed">
                    The laboratory results indicate elevated glycated hemoglobin (HbA1c) at 6.2%,
                    suggesting pre-diabetic range (5.7-6.4%). Additionally, LDL cholesterol is
                    significantly elevated at 160 mg/dL, indicating increased cardiovascular risk stratification.
                  </p>
                </div>

                <div>
                  <h3 className="font-bold mb-2" style={{ color: '#111827' }}>Recommendations</h3>
                  <ul className="text-gray-700 space-y-1 ml-4">
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      Immediate lifestyle modification interventions including dietary consultation
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      Structured physical activity program initiation
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      Nephrology consultation for elevated creatinine assessment
                    </li>
                  </ul>
                </div>

                <div>
                  <h3 className="font-bold mb-2" style={{ color: '#111827' }}>Follow-up</h3>
                  <p className="text-gray-700">
                    Repeat HbA1c in 3 months and lipid profile reassessment in 6-8 weeks post-intervention.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Auto-Referral Panel */}
          <div className="mb-8">
            <div
              className="p-4 rounded-lg flex items-center gap-3"
              style={{ backgroundColor: '#DBEAFE' }}
            >
              <CheckCircleIcon className="w-6 h-6 text-blue-600 flex-shrink-0" />
              <div>
                <div className="font-semibold text-blue-900">
                  🚀 Referral Booked ➜ Nephrology
                </div>
                <div className="text-blue-700 text-sm">
                  Appointment: 04 Jul 2025 • 10:00 AM • KFSH, Clinic B
                </div>
              </div>
            </div>
          </div>

          {/* Patient-Friendly Story Summary */}
          <div className="mb-8">
            <div
              className="p-6 rounded-xl"
              style={{ backgroundColor: '#F3F4F6' }}
            >
              <h2 className="text-xl font-semibold mb-4" style={{ color: '#111827' }}>
                What do these results mean for me?
              </h2>

              <div className="space-y-4">
                <div className="p-4 bg-white rounded-lg">
                  <div className="text-sm font-medium text-blue-600 mb-2">ENGLISH</div>
                  <p className="text-gray-700 leading-relaxed">
                    Imagine your red-blood cells as tiny ships carrying sugar on a three-month voyage.<br />
                    Today we discovered they're bringing <em>just a little</em> too much cargo (HbA1c 6.2 %).<br />
                    It's not a crisis, but it's a whisper from your body saying "ease off the sugar."<br />
                    Picture swapping one soda for water and strolling 30 minutes each evening—<br />
                    that simple habit can steer your ship back on course.
                  </p>
                </div>

                <div className="p-4 bg-white rounded-lg text-right" dir="rtl">
                  <div className="text-sm font-medium text-teal-600 mb-2">العَرَبِيَّة</div>
                  <p className="text-gray-700 leading-relaxed">
                    تخيَّل خلايا دمك الحمراء كسفن صغيرة تحمل السكر في رحلةٍ تمتدّ لثلاثة أشهر.<br />
                    اكتشفنا اليوم أن السفن محمَّلة <em>بزيادة طفيفة</em> (هيموغلوبين سكّر 6.2 ٪).<br />
                    ليست حالة طارئة، لكنها همسة من جسدك: "قَلِّل السكر قليلًا."<br />
                    جرّب استبدال مشروب غازي بكوب ماء والمشي 30 دقيقة مساءً—<br />
                    هذه الخطوة البسيطة قد تعيد السفن إلى مسارها الصحيح.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Digital Access Footer */}
          <div className="mb-8">
            <div className="flex items-center gap-6">
              <div
                className="w-18 h-18 border-2 border-dashed border-gray-400 rounded-lg flex items-center justify-center"
                style={{ width: '72px', height: '72px' }}
              >
                <div className="text-4xl">⚏</div>
              </div>
              <div>
                <h3 className="font-bold mb-1" style={{ color: '#111827' }}>
                  Scan to view full history & trends
                </h3>
                <p className="text-sm text-gray-600">
                  Access complete medical records, trending data, and detailed AI analysis reports
                  through our secure patient portal.
                </p>
              </div>
            </div>
          </div>

          {/* Page Footer */}
          <div className="border-t border-gray-300 pt-4">
            <div className="text-center text-xs text-gray-500 mb-2">
              Generated by Baseerah AI | HIPAA & SFDA SaMD Ready | Report ID RPT-1750781784537
            </div>
            <div
              className="border-t pt-2 text-center text-sm text-gray-600"
              style={{ borderColor: '#E5E7EB' }}
            >
              Page 1 of 1
            </div>
          </div>
        </motion.div>
      </div>

      {/* Print Styles */}
      <style>{`
        @media print {
          body { margin: 0; }
          .p-6 { display: none; }
          .bg-white { box-shadow: none !important; }
        }
      `}</style>
      </div>
    </div>
  );
};

export default LabReportDemo;