import { InputOTPForm } from "../../AppComponents/Forms/OtpForm";
import { useEffect } from "react";
import { toast } from "sonner";
import useAuthStore from "../../store/authStore";

export default function OtpPage() {
  const message = useAuthStore((state) => state.message);

  useEffect(() => {
    if (message) {
      toast.success(message);
    }
  }, [message]);
  return (
    <div className="w-full">
      <InputOTPForm />
    </div>
  );
}
