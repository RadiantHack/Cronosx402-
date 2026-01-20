import { TectonicSupplyComponent } from "./tectonic-supply";
import { TectonicBorrowComponent } from "./tectonic-borrow";
import { TectonicRepayComponent } from "./tectonic-repay";
import { TectonicWithdrawComponent } from "./tectonic-withdraw";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { useState } from "react";

interface LendBorrowPanelProps {
  userAddress?: string;
}

export default function LendBorrowPanel({ userAddress }: LendBorrowPanelProps) {
  const [activeTab, setActiveTab] = useState("supply");
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm mt-6">
      <Tabs defaultValue="supply" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="flex border-b border-slate-200 rounded-t-lg bg-slate-50">
          <TabsTrigger value="supply" className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-green-600 data-[state=active]:text-green-600 data-[state=active]:bg-white text-slate-600 rounded-none">📥 Supply</TabsTrigger>
          <TabsTrigger value="borrow" className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 data-[state=active]:bg-white text-slate-600 rounded-none">🏦 Borrow</TabsTrigger>
          <TabsTrigger value="repay" className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-purple-600 data-[state=active]:text-purple-600 data-[state=active]:bg-white text-slate-600 rounded-none">💳 Repay</TabsTrigger>
          <TabsTrigger value="withdraw" className="flex-1 px-4 py-3 text-center font-medium text-sm data-[state=active]:border-b-2 data-[state=active]:border-orange-600 data-[state=active]:text-orange-600 data-[state=active]:bg-white text-slate-600 rounded-none">📤 Withdraw</TabsTrigger>
        </TabsList>
        <div className="p-6">
          <TabsContent value="supply">
            <TectonicSupplyComponent userAddress={userAddress} active={activeTab === "supply"} />
          </TabsContent>
          <TabsContent value="borrow">
            <TectonicBorrowComponent userAddress={userAddress} active={activeTab === "borrow"} />
          </TabsContent>
          <TabsContent value="repay">
            <TectonicRepayComponent userAddress={userAddress} active={activeTab === "repay"} />
          </TabsContent>
          <TabsContent value="withdraw">
            <TectonicWithdrawComponent userAddress={userAddress} active={activeTab === "withdraw"} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
