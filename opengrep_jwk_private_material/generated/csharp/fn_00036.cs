using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"aXivpMEZcdL5","alg":"RS256","n":"6mfMYwbpCPiMJp3IFPSsUjVgARThHxoy5XtIG2Zr5GbXlky9","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"aXivpMEZcdL5\",\"alg\":\"RS256\",\"n\":\"6mfMYwbpCPiMJp3IFPSsUjVgARThHxoy5XtIG2Zr5GbXlky9\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
