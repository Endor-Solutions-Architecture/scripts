import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"tX-XtGYOKk_r","alg":"RS256","n":"2iqpt4kNOm46ywaN-N_J7HEzWqvq8mMEE4hSNujznUPomje1","e":"AQAB","p":"oY088C7QDCFgeQtb2xzemEiLSR78ijLLAU0KwiBKt2hRkURI","q":"q0wyNPt-uakuIYWZRy4Wu70ilh_C4Gtfy9-VQ891iSpBFVRv","dp":"ETkim4ctjAyCJ2PXrmyUxR7mbUWAoN17Dm4cggGlBLn7oRqy","dq":"idcKwqT9FAbjkQ_7Sws8sGac61fTv9agzg6RA8J73fAVo91y"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"tX-XtGYOKk_r\",\"alg\":\"RS256\",\"n\":\"2iqpt4kNOm46ywaN-N_J7HEzWqvq8mMEE4hSNujznUPomje1\",\"e\":\"AQAB\",\"p\":\"oY088C7QDCFgeQtb2xzemEiLSR78ijLLAU0KwiBKt2hRkURI\",\"q\":\"q0wyNPt-uakuIYWZRy4Wu70ilh_C4Gtfy9-VQ891iSpBFVRv\",\"dp\":\"ETkim4ctjAyCJ2PXrmyUxR7mbUWAoN17Dm4cggGlBLn7oRqy\",\"dq\":\"idcKwqT9FAbjkQ_7Sws8sGac61fTv9agzg6RA8J73fAVo91y\"}";
    JWK.parse(jwk);
  }
}
