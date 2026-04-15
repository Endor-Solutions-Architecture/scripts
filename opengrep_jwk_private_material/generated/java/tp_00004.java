import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"aSizP_Vw6-As","alg":"RS256","n":"7TBO9TYroWDuPNPARGqSp83XFbbqlqC3VNbLF7uxbLMn8RJ6","e":"AQAB","d":"udwT2equ"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"aSizP_Vw6-As\",\"alg\":\"RS256\",\"n\":\"7TBO9TYroWDuPNPARGqSp83XFbbqlqC3VNbLF7uxbLMn8RJ6\",\"e\":\"AQAB\",\"d\":\"udwT2equ\"}";
    JWK.parse(jwk);
  }
}
