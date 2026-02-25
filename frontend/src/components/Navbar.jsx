import { Link } from 'react-router-dom';
import useAuth from '../hooks/useAuth';

function Navbar() {
    const { isAuthenticated, logout } = useAuth();

    return (
        <nav className="navbar">
            <div className="navbar-brand">
                <Link to="/">SimuOrg</Link>
            </div>
            <div className="navbar-links">
                <Link to="/">Dashboard</Link>
                <Link to="/simulation">Simulation</Link>
                <Link to="/upload">Upload</Link>
                {isAuthenticated ? (
                    <button onClick={logout} className="btn-logout">Logout</button>
                ) : (
                    <Link to="/login">Login</Link>
                )}
            </div>
        </nav>
    );
}

export default Navbar;
