import { Outlet } from "react-router";
import Navbar from "../AppComponents/Navbar";
import Footer from "../AppComponents/Footer";

const RootLayout = () => {
  return (
    <>
      <Navbar />
      <div className="max-w-[80%] mx-auto my-10">
        <Outlet />
      </div>
      <Footer />
    </>
  );
};

export default RootLayout;
