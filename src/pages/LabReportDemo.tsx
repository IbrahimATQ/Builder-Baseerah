import React from "react";
import { motion } from "framer-motion";
import { ArrowLeftIcon, QrCodeIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";

const LabReportDemo = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white text-black p-8">
      {/* Back to Dashboard */}
      <motion.button
        onClick={() => navigate("/")}
        className="flex items-center gap-2 mb-6 px-4 py-2 bg-medical-blue text-white rounded-lg hover:bg-medical-blue/80 transition-colors"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        <ArrowLeftIcon className="w-4 h-4" />
        Back to Dashboard
      </motion.button>

      {/* PDF-Style Layout */}
      <motion.div
        className="max-w-4xl mx-auto bg-white border border-gray-300 shadow-xl"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{ minHeight: "297mm", width: "210mm" }} // A4 proportions
      >
        {/* Header */}
        <div className="border-b-2 border-gray-300 p-8">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-medical-blue mb-2">
                Baseerah Technologies
              </h1>
              <p className="text-gray-600">AI-Powered Lab Interpretation</p>
            </div>
            <div className="text-right text-sm">
              <div className="font-semibold">Patient ID: #12847</div>
              <div className="text-gray-600">
                Report Date: {new Date().toLocaleDateString()}
              </div>
              <div className="text-gray-600">
                Generated: {new Date().toLocaleString()}
              </div>
            </div>
          </div>
        </div>

        {/* Section 1: Patient Demographics */}
        <div className="p-8 border-b border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            Patient Demographics
          </h2>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="mb-2">
                <span className="text-gray-600">Name:</span>
                <span className="ml-2 font-medium">Ahmed Al-Mansouri</span>
              </div>
              <div className="mb-2">
                <span className="text-gray-600">Age:</span>
                <span className="ml-2 font-medium">45 years</span>
              </div>
              <div className="mb-2">
                <span className="text-gray-600">Gender:</span>
                <span className="ml-2 font-medium">Male</span>
              </div>
            </div>
            <div>
              <div className="mb-2">
                <span className="text-gray-600">MRN:</span>
                <span className="ml-2 font-medium">MRN-2024-12847</span>
              </div>
              <div className="mb-2">
                <span className="text-gray-600">Collection Date:</span>
                <span className="ml-2 font-medium">
                  {new Date().toLocaleDateString()}
                </span>
              </div>
              <div className="mb-2">
                <span className="text-gray-600">Ordering Physician:</span>
                <span className="ml-2 font-medium">Dr. Sarah Al-Zahra</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Lab Results Table */}
        <div className="p-8 border-b border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            Laboratory Results
          </h2>
          <table className="w-full border-collapse border border-gray-300">
            <thead>
              <tr className="bg-gray-100">
                <th className="border border-gray-300 p-3 text-left font-semibold">
                  Test
                </th>
                <th className="border border-gray-300 p-3 text-left font-semibold">
                  Result
                </th>
                <th className="border border-gray-300 p-3 text-left font-semibold">
                  Reference Range
                </th>
                <th className="border border-gray-300 p-3 text-center font-semibold">
                  Status
                </th>
                <th className="border border-gray-300 p-3 text-left font-semibold">
                  Units
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="border border-gray-300 p-3 font-medium">
                  HbA1c
                </td>
                <td className="border border-gray-300 p-3 font-mono">6.2</td>
                <td className="border border-gray-300 p-3">4.0 - 5.6</td>
                <td className="border border-gray-300 p-3 text-center">
                  <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-sm">
                    High
                  </span>
                </td>
                <td className="border border-gray-300 p-3">%</td>
              </tr>
              <tr className="bg-gray-50">
                <td className="border border-gray-300 p-3 font-medium">
                  LDL Cholesterol
                </td>
                <td className="border border-gray-300 p-3 font-mono">160</td>
                <td className="border border-gray-300 p-3">&lt; 100</td>
                <td className="border border-gray-300 p-3 text-center">
                  <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-sm">
                    Critical
                  </span>
                </td>
                <td className="border border-gray-300 p-3">mg/dL</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Section 3: AI Interpretation */}
        <div className="p-8 border-b border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            AI Clinical Interpretation
          </h2>
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
            <div className="flex items-center mb-2">
              <span className="text-sm font-medium text-blue-700">
                AI Confidence: 94%
              </span>
            </div>
          </div>
          <p className="text-gray-700 leading-relaxed mb-4">
            <strong>Clinical Summary:</strong> The laboratory results indicate
            elevated glycated hemoglobin (HbA1c) at 6.2%, suggesting
            pre-diabetic range (5.7-6.4%). Additionally, LDL cholesterol is
            significantly elevated at 160 mg/dL, indicating increased
            cardiovascular risk stratification.
          </p>
          <p className="text-gray-700 leading-relaxed mb-4">
            <strong>Recommendations:</strong> Immediate lifestyle modification
            interventions are indicated, including dietary consultation for
            carbohydrate restriction and structured physical activity program.
            The elevated creatinine levels warrant nephrology consultation to
            rule out diabetic nephropathy and assess renal function trajectory.
          </p>
          <p className="text-gray-700 leading-relaxed">
            <strong>Follow-up:</strong> Repeat HbA1c in 3 months to assess
            glycemic control response. Lipid profile reassessment in 6-8 weeks
            post-intervention initiation. Consider metformin initiation per
            clinical guidelines if lifestyle modifications insufficient.
          </p>
        </div>

        {/* Section 4: QR Code */}
        <div className="p-8">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            Digital Access
          </h2>
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 bg-gray-200 border-2 border-dashed border-gray-400 rounded-lg flex items-center justify-center">
              <QrCodeIcon className="w-12 h-12 text-gray-400" />
            </div>
            <div>
              <p className="text-gray-700 mb-2">
                <strong>Scan for full history</strong>
              </p>
              <p className="text-sm text-gray-600">
                Access complete medical records, trending data, and detailed AI
                analysis reports through our secure patient portal.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 p-4 bg-gray-50 text-center text-xs text-gray-600">
          <p>
            This report was generated by Baseerah Technologies AI System | HIPAA
            Compliant | SFDA SaMD Ready
          </p>
          <p className="mt-1">
            Report ID: RPT-{Date.now()} | Generated on{" "}
            {new Date().toLocaleString()}
          </p>
        </div>
      </motion.div>

      {/* Hidden improvement annotations (not visible to end-users) */}
      <div style={{ display: "none" }}>
        {/* FUTURE ENHANCEMENTS:
        - Add trend-line spark charts beside each lab value once longitudinal data exists
        - Surface patient-specific lifestyle tips fed by knowledge base v2
        - Integrate in-app chat with referral clinic for real-time confirmations
        - Provide one-click WhatsApp share of the Patient-Friendly Summary */}
      </div>
    </div>
  );
};

export default LabReportDemo;
