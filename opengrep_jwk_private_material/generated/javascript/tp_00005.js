import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"Mo_5d-TVfMUX","alg":"RS256","n":"_I355LpgyDiF85XCj9aE0XekLXnqYs4Ic2Y6vJKdMH3-jscf","e":"AQAB","d":"by9UhrGeizXO39nIq5Y28zB7VZ4mVe-Yc5bEh1W0edZmpKGOLh7kASg8VD0zZnMr"}
const key5 = {"kty":"RSA","kid":"Mo_5d-TVfMUX","alg":"RS256","n":"_I355LpgyDiF85XCj9aE0XekLXnqYs4Ic2Y6vJKdMH3-jscf","e":"AQAB","d":"by9UhrGeizXO39nIq5Y28zB7VZ4mVe-Yc5bEh1W0edZmpKGOLh7kASg8VD0zZnMr"};
void importJWK(key5, 'RS256');
